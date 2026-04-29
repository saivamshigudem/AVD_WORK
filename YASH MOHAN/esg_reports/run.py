import os
import sys
import subprocess

def check_ollama():
    """
    Checks if Ollama is running and if required models are present.
    """
    print("   [System] Checking Local LLM (Ollama)...", end="", flush=True)
    try:
        # Check connection (simple curl/access)
        try:
            # Added timeout to prevent hanging
            subprocess.run(["ollama", "list"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except subprocess.TimeoutExpired:
            print("\n   [Error] Ollama check TIMED OUT. Is the server responsive?")
            sys.exit(1)
        except:
            print("\n   [Error] Ollama is NOT running. Please run 'ollama serve' in a separate terminal.")
            sys.exit(1)
            
        print(" Connected.", flush=True)
        
        # Check Models
        required = ["llama3", "nomic-embed-text"]
        list_output = subprocess.check_output(["ollama", "list"]).decode()
        
        for model in required:
            if model not in list_output:
                print(f"\n   [Setup] Model '{model}' missing. Pulling...", flush=True)
                subprocess.run(["ollama", "pull", model], check=True)
                print(f"   [Setup] '{model}' ready.")
            else:
                print(f"\n   [Check] '{model}' found.", end="")
        print("\n")
                
    except FileNotFoundError:
        print("\n   [Error] 'ollama' command not found. Please install Ollama from https://ollama.com/")
        sys.exit(1)
    except Exception as e:
        print(f"\n   [Error] Unexpected error checking Ollama: {e}")
        # Don't exit, might be a minor issue
        pass

def main():
    print("\n===================================================")
    print("     🌿 ESG Analyser - Application Launcher")
    print("===================================================\n", flush=True)

    # 1. Check Ollama Service & Models
    check_ollama()

    # 2. Run Data Processing
    run_ingest = True
    print("\n[Data] forcing re-processing to ensure code sync.", flush=True)

    if run_ingest:
        print("\n[1/2] Processing Data (Parsing & Indexing)...")
        print("---------------------------------------------", flush=True)
        ingest_script = os.path.join("src", "ingest", "prepare_demo.py")
        try:
            # Add current directory to PYTHONPATH so "src" module is found
            env_vars = os.environ.copy()
            env_vars["PYTHONPATH"] = os.getcwd() + os.pathsep + env_vars.get("PYTHONPATH", "")
            
            # Pass modified env
            code = subprocess.call([sys.executable, ingest_script], env=env_vars)
            if code != 0:
                print(f"\n[Warning] Data processing script exited with code {code}.", flush=True)
                proceed = input("Continue to dashboard anyway? (y/n): ").strip().lower()
                if proceed != 'y':
                    sys.exit(1)
        except Exception as e:
            print(f"Error runing ingest script: {e}", flush=True)
            sys.exit(1)
    else:
        print("\n[1/2] Skipping Data Processing (using cached data).", flush=True)

    # 3. Run Dashboard
    print("\n[2/2] Launching Streamlit Dashboard...", flush=True)
    print("--------------------------------------", flush=True)
    dashboard_script = "esg_dashboard.py"
    try:
        subprocess.call([sys.executable, "-m", "streamlit", "run", dashboard_script], env=os.environ)
    except KeyboardInterrupt:
        print("\nStopping dashboard...", flush=True)

if __name__ == "__main__":
    main()
