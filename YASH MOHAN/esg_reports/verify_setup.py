
import os
import sys
import json

# Add current dir to path
sys.path.append(os.getcwd())

def check_file(path, name):
    if os.path.exists(path):
        print(f"[OK] {name} exists.")
        return True
    else:
        print(f"[FAIL] {name} missing at {path}")
        return False

def check_json(path, name):
    if check_file(path, name):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json.load(f)
            print(f"[OK] {name} is valid JSON.")
            return True
        except Exception as e:
            print(f"[FAIL] {name} is invalid JSON: {e}")
            return False
    return False

print("--- Checking Files ---")
check_json('parsed_structured.json', 'Parsed Data')
check_json('metrics.json', 'Metrics Data')
check_json('vector_store.json', 'Vector Store')

print("\n--- Checking Imports ---")
try:
    print("Importing LocalVectorStore...")
    from src.embeddings.local_store import LocalVectorStore
    print("[OK] LocalVectorStore imported.")
except Exception as e:
    print(f"[FAIL] LocalVectorStore import failed: {e}")

try:
    print("Importing Workflow...")
    from src.graph.workflow import build_esg_graph
    print("[OK] Workflow imported.")
except Exception as e:
    print(f"[FAIL] Workflow import failed: {e}")

print("\n--- Checking Instantiation ---")
try:
    print("Instantiating LocalVectorStore (this might load models)...")
    store = LocalVectorStore(persist_directory='vector_store.json')
    print(f"[OK] LocalVectorStore instantiated with {len(store.data)} entries.")
except Exception as e:
    print(f"[FAIL] LocalVectorStore instantiation failed: {e}")

try:
    print("Building Graph...")
    app = build_esg_graph()
    print("[OK] Graph built successfully.")
except Exception as e:
    print(f"[FAIL] Graph build failed: {e}")

print("\n--- Done ---")
