import json
import os
from typing import List, Dict, Any, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pathlib import Path

# Use relative import if running as module, or robust path handling
# For simplicity in this project structure, we import the class we just modified
from src.embeddings.local_store import LocalVectorStore

# -----------------------------------------------------------------------------
# SETUP & DATA LOADING
# -----------------------------------------------------------------------------
# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PARSED_PATH = REPO_ROOT / "data" / "processed" / "parsed_structured.json"
METRICS_PATH = REPO_ROOT / "data" / "processed" / "metrics.json"

# Global Caches
cached_parsed = {}
cached_metrics = {}

def load_data():
    """
    Loads parsed JSON data into global memory for quick access.
    """
    global cached_parsed, cached_metrics
    
    # Load Parsed Text & Tables
    if PARSED_PATH.exists():
        try:
            with open(PARSED_PATH, 'r', encoding='utf-8') as f:
                cached_parsed = json.load(f)
            print(f"[Graph] Loaded {len(cached_parsed)} parsed reports from {PARSED_PATH}")
        except Exception as e:
            print(f"[Graph] Error loading parsed data: {e}")
            
    # Load Metrics
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, 'r', encoding='utf-8') as f:
                cached_metrics = json.load(f)
            print(f"[Graph] Loaded metrics for {len(cached_metrics)} companies.")
        except Exception as e:
            print(f"[Graph] Error loading metrics: {e}")

load_data()

# Initialize Vector Store (Lazy load might be better but for now distinct instance)
# Note: Streamlit might reload this module. Ideally we cache this instance.
# But for now, we instantiate chunks.
store = None
def get_store():
    global store
    if store is None:
        store = LocalVectorStore(persist_directory=str(REPO_ROOT / "vector_store.json"))
    return store

# -----------------------------------------------------------------------------
# GRAPH STATE
# -----------------------------------------------------------------------------
class AgentState(TypedDict):
    question: str
    company: str
    intent: str  # 'general', 'comparison', 'extraction', 'full_report'
    documents: List[str]
    structured_tables: List[Dict]
    analysis: str
    final_answer: str
    steps: List[str]  # Trace of modules/files used during execution

# -----------------------------------------------------------------------------
# NODES
# -----------------------------------------------------------------------------

def router_node(state: AgentState) -> Dict:
    """
    Decides the next step based on user question keywords.
    """
    print("--- 1. [Router Node] Analyzing Intent ---")
    steps = state.get("steps", [])
    steps.append("1. [Router Node] Analyzing Intent (Logic: Internal)")
    
    q = state['question'].lower()
    
    if "compare" in q or "vs " in q or "versus" in q or "difference" in q:
        return {"intent": "comparison", "steps": steps}
    elif "table" in q or "row" in q or "csv" in q or "data" in q:
        # If they ask for data/tables, we try extraction
        return {"intent": "extraction", "steps": steps}
    elif "report" in q and ("full" in q or "entire" in q or "show" in q):
        return {"intent": "full_report", "steps": steps}
    elif "summarize" in q or "summary" in q or "overview" in q:
        # If they ask for a summary, we treat it as GENERAL retrieval but ensure we filter
        # OR we could have a specific 'summary' node. For now, let's treat it as general 
        # but the retrieval node will now use the company filter to find relevant chunks.
        return {"intent": "general", "steps": steps}
    else:
        return {"intent": "general", "steps": steps}

def retrieval_node(state: AgentState) -> Dict:
    """
    Uses the local embedding store to find relevant text chunks.
    Now uses HYBRID SEARCH (Metric + Keywords).
    """
    print("--- 2. [Retriever Node] Hybrid Search ---")
    steps = state.get("steps", [])
    steps.append("2. [Retriever Node] Hybrid Search (Vector + BM25) (Source: src/embeddings/local_store.py)")
    
    st = get_store()
    q = state['question']
    comp = state.get('company')
    
    docs = []
    
    search_query = q
    
    # ACCURACY: Extract Year from query for strict filtering
    import re
    filter_year = None
    year_match = re.search(r'\b(202[0-9]|2030)\b', q)
    if year_match:
        filter_year = year_match.group(1)
        print(f"   [Retriever] Detected Year Filter: {filter_year}")
    
    # OPTIMIZATION: If user asks for summary, we explicitly fetch the report start.
    # This guarantees the "Introduction" or "Executive Summary" is available.
    if "summarize" in q.lower() or "summary" in q.lower() or "overview" in q.lower():
         print("   [Retriever] Detected summary intent -> Injecting Report Introduction.")
         search_query = "Executive letter summary performance highlights 2025 goals strategy"
         
         if comp and comp in cached_parsed:
             full_text = cached_parsed[comp].get('text', '')
             if full_text:
                 # Inject first 3000 chars which usually contains the Executive Summary
                 intro_snippet = f"--- REPORT INTRODUCTION / EXECUTIVE SUMMARY ---\n{full_text[:3000]}"
                 docs.append(intro_snippet)

    # Generate embedding locally
    emb = st.get_embedding(search_query)
    
    # Call Hybrid Search
    results = st.weighted_hybrid_search(
        query_text=search_query, 
        query_embedding=emb, 
        top_k=5, 
        bm25_weight=0.3,
        filter_filename=comp,
        filter_year=filter_year
    )
    
    if results and results['documents']:
        # Append source citation to docs
        raw_docs = results['documents'][0]
        metas = results['metadatas'][0]
        for i, d in enumerate(raw_docs):
            # Extract page number from chunk content if available
            page_match = re.search(r'--- Page (\d+) ---', d)
            if page_match:
                page_num = page_match.group(1)
                source_ref = f"[Source: Page {page_num}]"
            else:
                source_ref = f"[Source: Chunk {metas[i].get('chunk_index', '?')}]"
            docs.append(f"{d}\n{source_ref}")
        
    # FALLBACK: If we still have NO docs (search failed and no summary injection), 
    # force inject the start of the file so the LLM isn't blind.
    if not docs and comp and comp in cached_parsed:
        print("   [Retriever] Zero results found -> Fallback to using File Start.")
        full_text = cached_parsed[comp].get('text', '')
        if full_text:
             docs.append(f"--- REPORT CONTENT SNAPSHOT (Fallback) ---\n{full_text[:2000]}")
    
    return {"documents": docs, "steps": steps}

def table_extractor_node(state: AgentState) -> Dict:
    """
    Extracts structured tables for the specific company.
    """
    print("--- 2. [Table Extractor Node] ---")
    steps = state.get("steps", [])
    steps.append("2. [Table Extractor Node] Reading JSON Data (Source: parsed_structured.json)")
    
    comp = state['company']
    data = cached_parsed.get(comp, {})
    tables = data.get('tables', [])
    
    # Simple logic: return top tables. 
    # Improvement: Semantic search on table headers could be done here if needed.
    return {"structured_tables": tables[:5], "steps": steps} 

def comparison_node(state: AgentState) -> Dict:
    """
    Uses the global metrics.json to answer comparison questions.
    """
    print("--- 2. [Comparison Node] ---")
    steps = state.get("steps", [])
    steps.append("2. [Comparison Node] Reading Metrics (Source: metrics.json) & Querying LLM (Ollama)")
    
    q = state['question']
    
    # Prepare Context with Clean Names to ensure LLM uses them
    clean_metrics = {}
    for k, v in cached_metrics.items():
        # "Apple_2025_ESG.pdf" -> "Apple"
        clean_name = k.split('_')[0]
        clean_metrics[clean_name] = v
        
    context = "Comparative ESG Metrics:\n"
    context += json.dumps(clean_metrics, indent=2)
    
    try:
        # Switch to Local LLM (Ollama)
        from langchain_ollama import ChatOllama
        # Defaulting to llama3, user should have it pulled: `ollama pull llama3`
        llm = ChatOllama(model="llama3", temperature=0)
        
        msg = [
            SystemMessage(content="You are an expert ESG analyst. Compare the companies using their **specific names** provided in the data (e.g., 'Apple', 'Google').\n\nRULES:\n1. NEVER use aliases like 'Company A' or 'Company B'. Always use the actual name.\n2. Base comparisons strictly on the provided metrics.\n3. Highlight key differences and percentage variances.\n4. Ensure all figures are accurate."),
            HumanMessage(content=f"Metrics Context:\n{context}\n\nUser Question: {q}")
        ]
        resp = llm.invoke(msg)
        return {"final_answer": resp.content}
    except Exception as e:
        return {"final_answer": f"Error during comparison (Check if Ollama is running): {e}"}

def full_report_node(state: AgentState) -> Dict:
    """
    Returns the text of the report (truncated if necessary).
    """
    print("--- 2. [Full Report Node] ---")
    steps = state.get("steps", [])
    steps.append("2. [Full Report Node] Reading Full Text (Source: parsed_structured.json)")
    
    comp = state['company']
    data = cached_parsed.get(comp, {})
    text = data.get('text', "No text found.")
    
    return {"final_answer": f"DISPLAY_REPORT_FLAG\n\n{text[:5000]}", "steps": steps} 
    # Note: We might handle the UI display differently if the flag is present, 
    # instead of dumping raw text into the chat.

def generator_node(state: AgentState) -> Dict:
    """
    Generates the final natural language answer using RAG (Docs + Tables).
    """
    print("--- 3. [Generator Node] Synthesizing Answer ---")
    steps = state.get("steps", [])
    steps.append("3. [Generator Node] Synthesizing Answer (Source: Ollama LLM + Retrieved Context)")
    
    q = state['question']
    comp = state.get('company')
    docs = state.get('documents', [])
    tables = state.get('structured_tables', [])
    
    context = "Retrieved Text Sections:\n" + "\n\n".join(docs)

    # Inject structured metrics for the specific company if available
    if comp and comp in cached_metrics:
        context += f"\n\nHigh-Level ESG Metrics for {comp}:\n"
        context += json.dumps(cached_metrics[comp], indent=2)

    
    if tables:
        context += "\n\nRetrieved Tables Data (First 5 rows per table):\n"
        for i, t in enumerate(tables):
            rows = t.get('rows', []) if isinstance(t, dict) else t
            if rows:
                headers = list(rows[0].keys())
                context += f"\nTable {i+1}:\n" + " | ".join(headers) + "\n"
                for r in rows[:5]:
                     context += " | ".join(str(r.get(h,'')) for h in headers) + "\n"

    try:
        # Switch to Local LLM (Ollama)
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model="llama3", temperature=0)
        
        msg = [
            SystemMessage(content="You are an expert ESG Analyst. Your goal is to provide **comprehensive, detailed, and data-rich answers** based strictly on the provided context.\n\nGUIDELINES:\n1. **Detail is Key**: Do not summarize briefly. Explain the 'Why' and 'How'.\n2. **Use Data**: Cite specific numbers, years, and targets from the context.\n3. **Structure**: Use bullet points and paragraphs for readability.\n4. **Citations**: Refer to specific sections or tables where possible.\n5. If the context is missing specific details, state clearly what is missing."),
            HumanMessage(content=f"Context:\n{context}\n\nUser Question: {q}")
        ]
        print(f"[Generator] Invoking Llama3 with {len(context)} chars of context...")
        resp = llm.invoke(msg)
        print("[Generator] Response received.")
        return {"final_answer": resp.content}
    except Exception as e:
        # STABILITY: Graceful Degradation for Context Length Errors
        print(f"   [Generator] Error: {e}")
        if "context length" in str(e).lower() or "too many tokens" in str(e).lower() or len(context) > 10000:
             print("   [Generator] Trying fallback with truncated context...")
             try:
                 # Reduce context drastically to just the top doc
                 truncated_context = "Retrieved Sections (Truncated):\n" + (docs[0] if docs else "No info")
                 msg[1] = HumanMessage(content=f"Context:\n{truncated_context}\n\nUser Question: {q}")
                 resp = llm.invoke(msg)
                 return {"final_answer": resp.content + "\n\n*(Note: Answer generated with limited context due to length)*"}
             except Exception as inner_e:
                 return {"final_answer": f"Error: Could not generate answer even with truncated context. ({inner_e})"}
        
        return {"final_answer": f"Error generating response (Check if Ollama is running): {e}"}



def grader_node(state: AgentState) -> Dict:
    """
    Evaluates the quality of the generated answer.
    If 'Low Quality', it routes back to retrieval with a re-phrased query or gracefully fails.
    For this implementation, we will append a 'Refinement Needed' note.
    """
    answer = state.get("final_answer", "")
    steps = state.get("steps", [])
    
    # Check if answer suggests lack of knowledge
    failures = ["i don't know", "not mentioned", "no information", "cannot find"]
    if any(f in answer.lower() for f in failures) or len(answer) < 20:
         steps.append("4. [Grader Node] Answer Incomplete. Flagging for review.")
         state["analysis"] = "Low Quality"
    else:
         steps.append("4. [Grader Node] Answer Quality Check Passed.")
         state["analysis"] = "High Quality"
         
    return {"steps": steps}

# -----------------------------------------------------------------------------
# COMPILE GRAPH
# -----------------------------------------------------------------------------
def build_esg_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("router", router_node)
    
    # Retrieval Nodes
    workflow.add_node("retriever", retrieval_node)
    workflow.add_node("table_extractor", table_extractor_node)
    
    # Reasoning Nodes
    workflow.add_node("comparator", comparison_node)
    workflow.add_node("generator", generator_node)
    
    # Evaluation Node
    workflow.add_node("grader", grader_node)
    
    # Helper for full text (no reasoning needed)
    workflow.add_node("full_report", full_report_node)

    # Set Entry
    workflow.set_entry_point("router")
    
    # Conditional Routing (Step 1)
    def route_step(state):
        return state['intent']

    workflow.add_conditional_edges(
        "router",
        route_step,
        {
            "general": "retriever",
            "extraction": "table_extractor", 
            "comparison": "comparator",
            "full_report": "full_report"
        }
    )
    
    # Flow: Retrieval -> Generator -> Grader -> END
    workflow.add_edge("retriever", "generator")
    workflow.add_edge("table_extractor", "generator")
    
    workflow.add_edge("generator", "grader")
    workflow.add_edge("comparator", "grader") # Comparator also produces answers that need checking!
    
    # Edges to End
    workflow.add_edge("grader", END)
    workflow.add_edge("full_report", END)

    return workflow.compile()
