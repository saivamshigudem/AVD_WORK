import json
import os
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# ---------------------------------------------
# Load Environment Variables
# ---------------------------------------------
load_dotenv()  # Load variables from .env file

API_KEY = os.getenv("API_KEY")  # Retrieve the API key from environment variables

if not API_KEY:
    raise ValueError("API_KEY environment variable is not set. Please set it in the .env file.")

MODEL_NAME = "llama-3.3-70b-versatile"
OUTPUT_DIR = "outputs"

# ---------------------------------------------
# Load Constitution file
# ---------------------------------------------
def load_constitution(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------
# Load Spec.md file
# ---------------------------------------------
def load_spec(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------
# Load API Endpoints file
# ---------------------------------------------
def load_endpoints(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


# ---------------------------------------------
# Initialize LLM
# ---------------------------------------------
llm = ChatGroq(
    groq_api_key=API_KEY,
    model=MODEL_NAME,
    temperature=0
)


# ---------------------------------------------
# Prompt Template
# ---------------------------------------------
workflow_prompt = PromptTemplate(
    input_variables=["constitution", "spec", "endpoints"],
    template=""" 
You are a analysis  agent.

Your task:
- Analyze the application constitution (rules, principles, constraints)
- Analyze the application specification (features, APIs, flows)
- Analyze the provided API endpoints
- Produce a clear, step-by-step workflow of the application with a recommended API execution order

CONSTITUTION:
----------------
{constitution}

SPECIFICATION:
----------------
{spec}

API ENDPOINTS:
----------------
{endpoints}

OUTPUT FORMAT:
----------------
1. System Initialization
2. Actors Involved
3. Request Flow
4. Core Processing Logic
5. Validation & Governance
6. Error Handling
7. Final Response Flow
8. API Execution Order

Write the workflow in simple, clear bullet points.
"""
)


# ---------------------------------------------
# Workflow Agent
# ---------------------------------------------
def generate_workflow(constitution_path: str, spec_path: str, endpoints_path: str) -> str:
    constitution = load_constitution(constitution_path)
    spec = load_spec(spec_path)
    endpoints = load_endpoints(endpoints_path)

    chain = workflow_prompt | llm | StrOutputParser()

    return chain.invoke({
        "constitution": constitution,
        "spec": spec,
        "endpoints": "\n".join(endpoints)
    })


# ---------------------------------------------
# Save Output to File
# ---------------------------------------------
def save_workflow_to_file(workflow: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{OUTPUT_DIR}/application_workflow_{timestamp}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Application Workflow\n\n")
        f.write(workflow)

    return output_path


# ---------------------------------------------
# Main
# ---------------------------------------------
if __name__ == "__main__":
    constitution_file = "constitution.md"
    spec_file = "spec.md"
    endpoints_file = "endpoints.txt"

    workflow_output = generate_workflow(
        constitution_file,
        spec_file,
        endpoints_file
    )

    output_file = save_workflow_to_file(workflow_output)

    print("\n===== APPLICATION WORKFLOW GENERATED =====\n")
    print(workflow_output)
    print(f"\n✅ Workflow saved to: {output_file}")
