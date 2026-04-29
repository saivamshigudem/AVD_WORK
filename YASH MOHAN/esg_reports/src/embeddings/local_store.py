import os
import json
import uuid
import numpy as np
from typing import List, Dict, Any
# Using Ollama to avoid Torch/DLL issues on Windows

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 150) -> List[str]:
    if not text:
        return []
    
    # 1. Split into paragraphs
    paragraphs = text.split('\n\n')
    
    # 2. Iterate and build chunks
    chunks = []
    current_chunk = []
    current_length = 0
    
    for p in paragraphs:
        p_len = len(p)
        
        # 3. Handle specific case: single paragraph larger than chunk_size
        if p_len > chunk_size:
            # If current_chunk has data, flush it first
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
                
            # Split this huge paragraph into sub-chunks
            # We strictly slice by character count as a fallback to prevent 400 errors from Ollama
            start = 0
            while start < p_len:
                end = min(start + chunk_size, p_len)
                sub_p = p[start:end]
                chunks.append(sub_p)
                # Overlap logic for splitting large paragraphs could be complex, 
                # for now simple slice to ensure we don't drop data.
                start = end # No overlap within a huge paragraph for simplicity, or add overlap logic
            continue

        # 4. Standard accumulation
        if current_length + p_len > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0
            
        current_chunk.append(p)
        current_length += p_len
        
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks

def table_to_markdown(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    md = "| " + " | ".join(headers) + " |\n"
    md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for r in rows:
        md += "| " + " | ".join(str(r.get(h, "")) for h in headers) + " |\n"
    return md

class LocalVectorStore:
    """
    A lightweight, in-memory vector store using JSON and Numpy.
    Uses Ollama Embeddings to ensure full local compatibility and avoid DLL issues.
    """
    def __init__(self, persist_directory: str = "data/processed/vector_store.json"):
        """
        Initialize LocalVectorStore using Ollama and JSON persistence.
        """
        self.persist_file = persist_directory
        
        # Initialize Ollama Embeddings
        # User must run: `ollama pull nomic-embed-text`
        try:
            from langchain_ollama import OllamaEmbeddings
            self.model = OllamaEmbeddings(model="nomic-embed-text")
            # Nomic-embed-text is 768 dim, usually.
        except Exception as e:
            print(f"Failed to load OllamaEmbeddings: {e}")
            self.model = None

        # Structure: list of dicts { 'id': str, 'embedding': [float], 'metadata': dict, 'document': str }
        self.data = []
        self._load()

    def _load(self):
        if os.path.exists(self.persist_file):
            try:
                with open(self.persist_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                print(f"Loaded {len(self.data)} documents from {self.persist_file}")
                
                # Check dimension consistency
                if self.data and self.model:
                    try:
                        # Probe model dimension
                        test_emb = self.get_embedding("test")
                        if test_emb and len(self.data[0]['embedding']) != len(test_emb):
                            print(f"[WARNING] Vector store dimension ({len(self.data[0]['embedding'])}) "
                                  f"does not match current model dimension ({len(test_emb)}). "
                                  "Run 'Process & Index Reports' in the dashboard.")
                    except Exception:
                        pass
            except Exception as e:
                print(f"Failed to load vector store: {e}")
                self.data = []

    def _save(self):
        # STABILITY: Atomic write to prevent corruption
        import shutil
        temp_file = self.persist_file + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f)
            # Atomic rename (replace)
            if os.path.exists(self.persist_file):
                os.replace(temp_file, self.persist_file)
            else:
                os.rename(temp_file, self.persist_file)
        except Exception as e:
            print(f"Failed to save vector store: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def _generate_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def get_embedding(self, text: str) -> List[float]:
        if not self.model:
            return []
        try:
            # OllamaEmbeddings.embed_query returns a list of floats directly
            return self.model.embed_query(text)
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

    def index_structured_report(self, filename: str, structured: Dict[str, Any]):
        # Clear existing entries for this file to avoid duplicates on re-indexing
        self.data = [d for d in self.data if d['metadata'].get('filename') != filename]
        
        text = structured.get('text', '')
        if text:
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                emb = self.get_embedding(chunk)
                if not emb: continue
                
                # Extract year for metadata
                year = "Unknown"
                if "2024" in filename: year = "2024"
                elif "2025" in filename: year = "2025"
                elif "2023" in filename: year = "2023"
                
                msg = {
                    'id': self._generate_id(f"{filename}_chunk_{i}"),
                    'embedding': emb,
                    'document': chunk,
                    'metadata': {
                        'filename': filename,
                        'type': 'text',
                        'chunk_index': i,
                        'year': year
                    }
                }
                self.data.append(msg)
                if i % 10 == 0: print(f"Indexed chunk {i} for {filename}")

        # Index Semantic Tables (Better for RAG)
        semantic_tables = structured.get('semantic_tables', [])
        for i, stext in enumerate(semantic_tables):
            # Check length to prevent 400 error
            if len(stext) > 2000:
                # Truncate strictly for embedding safety
                safe_text = stext[:2000]
            else:
                safe_text = stext
                
            emb = self.get_embedding(safe_text)
            if not emb: continue
            
            msg = {
                'id': self._generate_id(f"{filename}_sem_table_{i}"),
                'embedding': emb,
                # Store FULL text in document, only truncate for embedding
                'document': stext, 
                'metadata': {
                    'filename': filename,
                    'type': 'semantic_table',
                    'chunk_index': i
                }
            }
            self.data.append(msg)
            print(f"Indexed semantic table {i} for {filename}")

        self._save()

    def query(self, query_embedding: List[float], top_k: int = 3) -> Dict[str, Any]:
        if not self.data:
            return {'documents': [], 'metadatas': []}
        
        q_vec = np.array(query_embedding)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return {'documents': [], 'metadatas': []}

        scores = []
        for item in self.data:
            d_vec = np.array(item['embedding'])
            d_norm = np.linalg.norm(d_vec)
            if d_norm == 0:
                sim = 0.0
            else:
                sim = np.dot(q_vec, d_vec) / (q_norm * d_norm)
            scores.append((sim, item))
        
        # Sort desc
        scores.sort(key=lambda x: x[0], reverse=True)
        top_hits = scores[:top_k]
        
        return {
            'documents': [[h[1]['document'] for h in top_hits]],
            'metadatas': [[h[1]['metadata'] for h in top_hits]]
        }

    def weighted_hybrid_search(self, query_text: str, query_embedding: List[float], top_k: int = 5, bm25_weight: float = 0.3, filter_filename: str = None, filter_year: str = None) -> Dict[str, Any]:
        """
        Combines Vector Similarity with BM25 Keyword Search.
        Score = (1 - weight) * VectorScore + weight * BM25Score
        OPTIMIZED: Uses NumPy vectorization and Caching.
        Added 'filter_filename' to restrict search to a specific company/file.
        """
        if not self.data: return {'documents': []}

        # Create a mask for filtered documents
        mask = np.ones(len(self.data), dtype=bool)
        
        # PRIMARY FILTER: Filename
        if filter_filename:
            for i, item in enumerate(self.data):
                if item['metadata'].get('filename') != filter_filename:
                    mask[i] = False
        
        # SECONDARY FILTER: Year (Accuracy Enhancement)
        if filter_year:
             for i, item in enumerate(self.data):
                # Only apply if the item HAS a year metadata, otherwise keep it (permissive)
                # or strict? Let's be strict if they asked for a year.
                meta_year = item['metadata'].get('year', 'Unknown')
                if meta_year != 'Unknown' and meta_year != filter_year:
                    mask[i] = False
        
        # If mask is all false (found nothing for this file), return empty
        if not np.any(mask):
            return {'documents': []}

        # 1. Vector Search Scores (Using NumPy vectorization for speed)
        q_vec = np.array(query_embedding)
        norm_q = np.linalg.norm(q_vec)
        
        # Optimize: Pre-compute matrix of all document embeddings
        # We cache the matrix and only rebuild if data count changes
        if not hasattr(self, '_doc_matrix') or len(self._doc_matrix) != len(self.data):
             self._doc_matrix = np.array([d['embedding'] for d in self.data])
             self._doc_norms = np.linalg.norm(self._doc_matrix, axis=1)
        
        # Cosine Similarity = (A . B) / (|A| * |B|)
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            vec_scores = np.dot(self._doc_matrix, q_vec) / (self._doc_norms * norm_q)
            vec_scores = np.nan_to_num(vec_scores) # Replace NaNs with 0
            
        # Normalize scores to 0-1
        if len(vec_scores) > 0:
            v_min, v_max = vec_scores.min(), vec_scores.max()
            if v_max - v_min > 0:
                vec_scores = (vec_scores - v_min) / (v_max - v_min)
            else:
                vec_scores[:] = 0.0

        # 2. BM25 Scores (Use Cached Object if possible)
        # We need to tokenize every time unless we cache the BM25 object
        # Since 'data' can change, we check if we need to rebuild
        if not hasattr(self, '_bm25') or len(self.data) != getattr(self, '_bm25_corpus_len', 0):
             try:
                 from rank_bm25 import BM25Okapi
                 # Simple tokenization: lower + split on space
                 docs = [d['document'] for d in self.data]
                 tokenized_corpus = [doc.lower().split(" ") for doc in docs]
                 self._bm25 = BM25Okapi(tokenized_corpus)
                 self._bm25_corpus_len = len(self.data)
             except ImportError:
                 self._bm25 = None
        
        bm25_scores = np.zeros(len(self.data))
        if self._bm25:
             tokenized_query = query_text.lower().split(" ")
             bm25_scores = np.array(self._bm25.get_scores(tokenized_query))
             
             # Normalize BM25
             if len(bm25_scores) > 0:
                 b_min, b_max = bm25_scores.min(), bm25_scores.max()
                 if b_max - b_min > 0:
                     bm25_scores = (bm25_scores - b_min) / (b_max - b_min)
                 else:
                     bm25_scores[:] = 0.0

        # 3. Combine
        final_scores = (1 - bm25_weight) * vec_scores + bm25_weight * bm25_scores
        
        # Apply filter mask (set scores of filtered-out docs to -infinity)
        final_scores[~mask] = -1.0
        
        # Get Top K indices
        # np.argsort returns indices that sort the array, in ascending order
        # We want descending, so we take the last k elements and reverse them
        # Note: filtered items will be at the bottom (< 0)
        top_indices = np.argsort(final_scores)[-top_k:][::-1]
        
        # Construct results
        documents = []
        metadatas = []
        scores_out = []
        
        for idx in top_indices:
            # Only include if score is valid (>= 0)
            if final_scores[idx] >= 0:
                documents.append(self.data[idx]['document'])
                metadatas.append(self.data[idx]['metadata'])
                scores_out.append(float(final_scores[idx]))
        
        return {
            'documents': [documents],
            'metadatas': [metadatas],
            'scores': scores_out
        }
