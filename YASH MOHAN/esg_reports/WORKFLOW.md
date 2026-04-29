0) Execution Flow (Start Here)
**Everything starts with:** `run.py`
This script triggers the entire chain reaction:
1.  **Entry Point:** The script sets up the local environment, checking if `ollama` service is running and if `llama3` + `nomic-embed-text` models are available (with timeouts to prevent hanging).
2.  **Data Processing:** It executes `src/ingest/prepare_demo.py` if needed.
    *   *Input:* PDFs in `data/raw/` (moved from `esg_reports/`).
    *   *Action:* Parses text (`pdfplumber`), cleans tables, extracts metrics using Regex (`metrics.py`), and generates embeddings (`local_store.py`).
    *   *Output:* Creates/Updates `data/processed/parsed_structured.json`, `metrics.json`, and `vector_store.json`.
3.  **User Interface:** It executes `streamlit run esg_dashboard.py`.
    *   *Input:* Reads the JSON files created in step 2.
    *   *Output:* Launches the web interface in your browser (http://localhost:8501).
**End State:** The user interacts with the dashboard; the LangGraph workflow handles all queries locally using the "AI Assistant".

1) Source PDFs
- Place ESG PDF reports in the `data/raw/` folder.
  - `data/raw/Apple_2025_ESG_Report.pdf`
  - `data/raw/Google_2025_ESG_Report.pdf`
  - `data/raw/Microsoft_2025_ESG_Report.pdf`
- The system automatically detects these during the ingestion phase.

2) Parsing & Extraction
- `src/parsers/parse_esg_reports.py`: Uses `pdfplumber` to extract page text and simple tables. It creates "Semantic Tables" (text descriptions of table rows) to improve RAG accuracy.
- `src/parsers/metrics.py`: Now uses a **Robust Regex Engine** (instead of LLM) to extract universal ESG metrics (Carbon, Energy, Water, Waste, Renewable %). It intelligently handles units in headers (e.g., "in millions") to ensure data accuracy.
- `clean_and_structure_tables`: Converts raw DataFrames into structured JSON and validates data quality.

3) Embeddings and Storage
- `src/embeddings/local_store.py`: Implements a **LocalVectorStore** using JSON + NumPy.
- **Atomic Saves:** Implements safe write operations (write-to-temp + rename) to prevent database corruption during crashes.
- **Embedding Model:** `nomic-embed-text` via Ollama.
- **Search Capabilities:**
    - **Hybrid Search:** Weighted combination of Vector Similarity + BM25 Keyword search.
    - **Precise Filtering:** Supports filtering by `filename` and `year` (automatically extracted from user query).
- **Improvements:**
    - **Safety Truncation:** Large chunks (e.g., massive tables) are truncated to 2000 characters before embedding to prevent `400 Bad Request` errors.
    - **Smart Chunking:** Text is split into paragraphs with overlap, handling giant paragraphs safely.

4) Question Answering (LangGraph Workflow)
- `src/graph/workflow.py`: The brain of the "ESG Analyser". Nodes include:
  - **router**: Analyzes intent. Handles:
    - *Comparison*: "Compare Apple vs Google"
    - *Extraction*: "Show me data tables"
    - *Full Report*: "Show full text"
    - *Summary*: "Summarize this report" -> triggers **Manual Injection** of the report introduction to guarantee high-quality summaries.
  - **retriever**: Performs **Hybrid Search** with strictly typed filtering (Company + Year). Includes automatic fallback to report introduction if search fails.
  - **table_extractor**: Fetches raw data tables.
  - **comparator**: Uses `llama3` to synthesize detailed comparison answers, highlighting leaders and laggards.
  - **generator**: RAG-based answer generation.
    - **Metric Injection**: Auto-injects high-level metrics (from `metrics.json`) into the prompt context for maximum accuracy.
    - **Graceful Degradation**: Automatically retries with truncated context if the LLM hits token limits.
  - **grader**: Quality check on answers.
- **LLM Model:** `llama3` via Ollama (Local).

5) Interfaces
- Streamlit Dashboard (`esg_dashboard.py`):
  - **Title**: "ESG Analyser".
  - **AI Assistant**: 
    - **Quick Prompts**: One-click pills for common queries (Summarize, Emissions, Goals).
    - **Context Inspector**: Expandable "View Source Context" to verify AI claims against raw text chunks.
    - **Enhanced Reports**: Clean, scrollable, and formatted display of full report text.
  - **Comparison Tab**: 
    - Visual charts for Carbon, Energy, Water, etc.
    - **CSV Export**: Download aggregated metrics for offline analysis.
  - **Deep Dive**: View raw formatted text and extracted tables.

6) Technology Stack
- **Embeddings:** `nomic-embed-text` (Ollama)
- **Vector Store:** Custom Local JSON Store (NumPy accelerated, Atomic Writes)
- **LLM:** `llama3` (Ollama)
- **Orchestration:** LangGraph
- **Frontend:** Streamlit
- **No external API keys required!**

7) How to run
**Use the consolidated python launcher:**
1. Ensure Ollama is running:
   ```powershell
   ollama serve
   ```
2. Run the start script in VS Code:
   ```powershell
   python run.py
   ```
   *This handles environment checks, data ingestion, and dashboard launch automatically.*

8) Notes and Troubleshooting
- **"Stuck" on Processing**: If the indexer seems stuck, it is likely processing a large PDF. We have optimized it with strict chunking limits to prevent crashes.
- **Missing Data**: If charts are empty, the Regex extractor might have missed a pattern. Check `metrics.json`.
- **Ollama Errors**: `run.py` now includes a timeout check to valid Ollama responsiveness on startup.


