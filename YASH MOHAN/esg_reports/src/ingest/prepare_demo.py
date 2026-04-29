import os
import json
from src.parsers.parse_esg_reports import parse_esg_reports, clean_and_structure_tables
from src.parsers.metrics import extract_key_metrics_from_structured

def main():
    reports_dir = 'data/raw'
    parsed = {}
    if not os.path.exists(reports_dir):
        print(f'No {reports_dir}/ directory found')
        return

    for f in os.listdir(reports_dir):
        if f.lower().endswith('.pdf'):
            path = os.path.join(reports_dir, f)
            print(f'Parsing {f}...')
            parsed[f] = parse_esg_reports(path)

    structured = clean_and_structure_tables(parsed)

    with open('data/processed/parsed_structured.json', 'w', encoding='utf-8') as fp:
        json.dump(structured, fp, ensure_ascii=False, indent=2)

    metrics = extract_key_metrics_from_structured(structured)
    with open('data/processed/metrics.json', 'w', encoding='utf-8') as mf:
        json.dump(metrics, mf, indent=2)

    print(f'Prepared demo: parsed {len(parsed)} reports; wrote parsed_structured.json and metrics.json')

    # Indexing for RAG
    try:
        from src.embeddings.local_store import LocalVectorStore
        print("Indexing reports into Local Vector Store...")
        # No API Key check needed for local embedding
        store = LocalVectorStore()
        for fname, content in structured.items():
            print(f"Indexing {fname}...")
            store.index_structured_report(fname, content)
        print("Indexing complete.")
    except Exception as e:
        print(f"Indexing failed: {e}")

if __name__ == '__main__':
    main()
