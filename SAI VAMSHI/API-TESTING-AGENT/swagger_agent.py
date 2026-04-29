import json
import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
load_dotenv() 
API_KEY = os.getenv("API_KEY")
OUTPUT_FILE = "generated_testcases.py"
WORKFLOW_MD_PATH = "output/outputs/application_workflow_20260112_042515.md"


# --------------------------------------------------
# LOAD FILES (PLAIN TEXT)
# --------------------------------------------------
def load_sample_values(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
            if not data:
                raise ValueError(f"The file at {path} is empty.")
            return data
    except Exception as e:
        print(f"Error loading {path}: {e}")
        raise


def load_endpoints(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading endpoints file {path}: {e}")
        raise


def load_latest_workflow_md(folder_path="outputs"):
    try:
        md_files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.endswith(".md")
        ]

        if not md_files:
            raise FileNotFoundError("No .md workflow files found in outputs folder")

        latest_file = max(md_files, key=os.path.getmtime)

        with open(latest_file, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                raise ValueError(f"{latest_file} is empty")

        print(f"📄 Using workflow file: {latest_file}")
        return content

    except Exception as e:
        print(f"❌ Error loading workflow markdown: {e}")
        raise



# --------------------------------------------------
# LLM INITIALIZATION
# --------------------------------------------------
llm = ChatGroq(
    groq_api_key=API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0
)


# --------------------------------------------------
# PROMPT
# --------------------------------------------------
prompt = PromptTemplate.from_template("""
You are an API test generator agent.
Your task is to generate pytest test cases for every API endpoint.
### API ENDPOINTS
{endpoints}
The above file contains all the API endpoints in the system. Generate pytest test cases for each endpoint using requests and pytest.
Below is the dataset that is used for the generation of test cases.
generate test case for each endpoint using this data.
{sample_values}
use this data to create test cases for all the endpoints mentioned above.
By considering into this create the test cases for all the endpoints
SEQUENCE OF TEST CASE GENERATION:
Create each test case for each endpoint 
donot create methods again and again.
generate agent values for agents endpoint and policy values for policies endpoint and same for all other endpoints.
First generate test case for POST endpoints for AGENTS,POLICIES,COMMISSIONS.
then do this as one testcase  -X PATCH "http://localhost:8080/api/api/v1/commissions/1/status?status=APPROVED" \
  -H "Content-Type: application/json"
    to change the status of commission to APPROVED.
then do this as one testcase  -X PATCH "http://localhost:8080/api/api/v1/commissions/1/status?status=PAID" \
  -H "Content-Type: application/json"
    to change the status of commission to PAID.
donot add the create_agent , create_policy , create_commission , create_payment methods again and again.
Then generate test case for POST endpoint for PAYMENTS.
Then generate test case for GET endpoints for AGENTS,POLICIES,COMMISSIONS,PAYMENTS.
Then generate test case for PUT endpoints for AGENTS,POLICIES,COMMISSIONS,PAYMENTS.
Then generate test case for DELETE endpoints for AGENTS,POLICIES,COMMISSIONS,PAYMENTS.
IMPORTANT NOTES:
use create agent in agent post methods only and 
add create methods in POST endpoints only, donot add to the  use other GET,PUT,DELETE endpoints .
use 204 status code for DELETE endpoints.
use data
DISCLAIMER:
                                      
use agent creation data for agent related endpoints only.
use policy creation data for policy related endpoints only. 
USE commission creation data for commission related endpoints only.
use payment creation data for payment related endpoints only.
{workflow_md}
### OUTPUT RULES
- The base URL for all endpoints is "http://localhost:8080/api/api"
- for actuator and health endpoints base url is "http://localhost:8080/api"
- dont create and consider the Authorization headers
- Output ONLY Python pytest code
- Use requests + pytest
- Create reusable helper methods if needed
- Assert HTTP status codes
- No markdown
- No explanations
""")


chain = prompt | llm | StrOutputParser()


# --------------------------------------------------
# TEST CASE GENERATION
# --------------------------------------------------
def generate_testcases(sample_values, endpoints, workflow_md):
    response = chain.invoke({
        "sample_values": sample_values,
        "endpoints": endpoints,
        "workflow_md": workflow_md
    })
    return response


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    sample_values = load_sample_values("swagger_post_apis_output.txt")
    endpoints = load_endpoints("endpoints.txt")
    workflow_md = load_latest_workflow_md("outputs")

    print(f"🧩 Sample data size: {len(sample_values)} chars")

    generated_code = generate_testcases(
        sample_values=sample_values,
        endpoints=endpoints,
        workflow_md=workflow_md
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(generated_code)

    print(f"✅ Test cases generated successfully → {OUTPUT_FILE}")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------
if __name__ == "__main__":
    main()
