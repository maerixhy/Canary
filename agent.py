import os
from elasticsearch import Elasticsearch
from google import genai

# Config
ES_URL = "https://my-elasticsearch-project-f4eb8f.kb.us-central1.gcp.elastic.cloud"
ES_API_KEY = "your-elastic-api-key-here"
PROJECT_ID = "continual-tine-493920-b1"
LOCATION = "us-central1"

# Initialize clients
es = Elasticsearch(ES_URL, api_key=ES_API_KEY)
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

def analyze_company(company_name: str) -> dict:
    """Core Canary function - analyzes a company and returns risk assessment"""
    
    try:
        results = es.search(
            index="canary-signals",
            body={
                "query": {
                    "match": {
                        "company": company_name
                    }
                }
            }
        )
        signals = results["hits"]["hits"]
    except:
        signals = []

    prompt = f"""
    You are Canary, a job offer intelligence agent.
    Analyze {company_name} based on these signals: {signals}
    
    Research the following and provide a risk assessment:
    1. Recent layoff history
    2. Funding status
    3. Leadership stability
    4. Job posting trends
    5. Employee sentiment
    
    Return a JSON with:
    - risk_score: RED, YELLOW, or GREEN
    - signals: list of specific findings
    - negotiation_tips: specific advice based on findings
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return {"company": company_name, "analysis": response.text}

if __name__ == "__main__":
    result = analyze_company("Google")
    print(result)