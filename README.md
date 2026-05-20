# 🐤 Canary — Job Offer Intelligence Platform

> **Know before you go.**

Canary is an AI-powered job intelligence platform that analyzes companies for job seekers — surfacing hiring signals, layoff history, funding status, and leadership stability — so you can negotiate smarter and protect yourself before signing an offer.

Built for the **Google Cloud + Elastic Hackathon 2026**.

---

## What it does

- **Analyze any company** — paste a company name and get a risk score (Stable / Caution / Volatile) with specific signal findings
- **Stage-aware advice** — different intelligence depending on whether you're applying, interviewing, or holding an offer
- **Live pipeline tracker** — track all your active companies with real-time signal updates
- **Offer playbook** — specific negotiation tactics based on what Canary finds
- **Signal memory** — prior analyses are stored in Elasticsearch and used to enrich future queries

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| AI Agent | Google Cloud Agent Builder + Gemini 2.5 Flash |
| Search & Storage | Elastic Cloud Serverless (Elasticsearch) |
| MCP Integration | Elastic Agent Builder MCP Server |
| Backend | Python + Flask |
| Frontend | Vanilla HTML/CSS/JS |
| Infrastructure | Google Cloud (Vertex AI, Cloud Run) |

---

## Architecture

```
User → Flask API → Gemini 2.5 Flash (Vertex AI)
                 ↕
         Elastic MCP Server
                 ↕
        Elasticsearch Index
        (canary-signals)
```

1. User submits a company name + stage
2. Flask calls Elasticsearch (via Elastic MCP) to retrieve any previously stored signals
3. Gemini analyzes the company using prior context + its knowledge
4. New signals are stored back to Elasticsearch via the MCP server
5. Structured JSON response rendered in the UI

---

## Setup

### Prerequisites
- Google Cloud account with Vertex AI enabled
- Elastic Cloud Serverless account
- Python 3.10+

### Environment variables

```bash
export ES_API_KEY="your-elastic-api-key"
export KIBANA_URL="https://your-project.kb.region.gcp.elastic.cloud"
export ES_URL="https://your-project.es.region.gcp.elastic.cloud"
export PROJECT_ID="your-gcp-project-id"
export LOCATION="us-central1"
```

### Install & run

```bash
pip install flask elasticsearch google-genai google-adk mcp
python app.py
```

Open `http://localhost:8080`

---

## Elastic MCP Integration

Canary connects to the Elastic Agent Builder MCP server at:
```
{KIBANA_URL}/api/agent_builder/mcp
```

The MCP server exposes Elasticsearch tools (search, index, list_indices) that the agent uses to retrieve and store company signals. This enables Canary to build a persistent signal memory — every analysis enriches the knowledge base for future queries.

---

## License

MIT — see [LICENSE](LICENSE)