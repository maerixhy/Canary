"""
Canary — Job Offer Intelligence Platform
Architecture:
  - Google ADK + Elastic MCP server for signal retrieval and storage
  - Gemini 2.5 Flash (Vertex AI) for structured risk analysis
  - Flask for serving the UI and REST API
"""
import os
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from elasticsearch import Elasticsearch
from google import genai

app = Flask(__name__, static_folder='.')

# ── CONFIG (from environment variables) ──
KIBANA_URL  = os.environ.get("KIBANA_URL",  "https://my-elasticsearch-project-f4eb8f.kb.us-central1.gcp.elastic.cloud")
ES_URL      = os.environ.get("ES_URL",      "https://my-elasticsearch-project-f4eb8f.es.us-central1.gcp.elastic.cloud")
ES_API_KEY  = os.environ.get("ES_API_KEY",  "")
ES_MCP_URL  = f"{KIBANA_URL}/api/agent_builder/mcp"
PROJECT_ID  = os.environ.get("PROJECT_ID",  "continual-tine-493920-b1")
LOCATION    = os.environ.get("LOCATION",    "us-central1")
INDEX       = "canary-signals"

# ── ELASTIC MCP CONNECTION (via ADK) ──
try:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams
    elastic_mcp = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=ES_MCP_URL,
            headers={"Authorization": f"ApiKey {ES_API_KEY}"}
        )
    )
    MCP_CONNECTED = True
    print(f"✅ Elastic MCP connected: {ES_MCP_URL}")
except Exception as e:
    MCP_CONNECTED = False
    print(f"⚠️  Elastic MCP: {e}")

# ── DIRECT ELASTIC CLIENT (for reliable index operations) ──
es = Elasticsearch(ES_URL, api_key=ES_API_KEY)

# ── GEMINI CLIENT ──
gemini = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# ── ENSURE INDEX ──
def ensure_index():
    try:
        if not es.indices.exists(index=INDEX):
            es.indices.create(index=INDEX, body={
                "mappings": {
                    "properties": {
                        "company":     {"type": "keyword"},
                        "signal_type": {"type": "keyword"},
                        "text":        {"type": "text"},
                        "val":         {"type": "keyword"},
                        "sentiment":   {"type": "keyword"},
                        "risk_score":  {"type": "keyword"},
                        "timestamp":   {"type": "date"}
                    }
                }
            })
            print(f"✅ Created index: {INDEX}")
    except Exception as e:
        print(f"Index note: {e}")

# ── SEARCH ELASTIC FOR EXISTING SIGNALS ──
def search_signals(company: str) -> list:
    try:
        result = es.search(index=INDEX, body={
            "query": {"match": {"company": company}},
            "size": 5,
            "sort": [{"timestamp": {"order": "desc"}}]
        })
        return [h["_source"] for h in result["hits"]["hits"]]
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ── STORE SIGNALS IN ELASTIC ──
def store_signals(company: str, signals: list, risk_score: str):
    try:
        for s in signals:
            es.index(index=INDEX, body={
                "company":     company,
                "signal_type": s.get("label", "general"),
                "text":        s.get("text", ""),
                "val":         s.get("val", ""),
                "sentiment":   s.get("type", "ok"),
                "risk_score":  risk_score,
                "timestamp":   datetime.utcnow().isoformat()
            })
        print(f"✅ Stored {len(signals)} signals for {company}")
    except Exception as e:
        print(f"Store error: {e}")

# ── ANALYZE COMPANY ──
def analyze_company(company: str, stage: str, offer_text: str = "") -> dict:

    # Pull existing signals from Elastic
    existing = search_signals(company)
    context = ""
    if existing:
        context = f"\nPreviously stored signals for {company}: {json.dumps(existing[:3])}"

    stage_ctx = {
        "applying":     "The user is deciding whether to apply. Give advice on whether to pursue.",
        "interviewing": "The user is actively interviewing. Give advice on red flags and smart questions to ask.",
        "offer":        f"The user has received an offer. Focus on negotiation strategy. {('Offer details: ' + offer_text) if offer_text else ''}"
    }.get(stage, "")

    prompt = f"""You are Canary, a job intelligence agent that analyzes companies for job seekers.

Analyze: {company}
Context: {stage_ctx}
{context}

Return ONLY a valid JSON object. No markdown, no explanation, no code blocks.

{{
  "risk_score": "stable",
  "new_signal": "<strong>Key finding:</strong> One specific recent insight about this company.",
  "sector": "Industry sector name",
  "metrics": [
    {{"val": "↑8%",  "label": "Hiring vel.", "delta": "vs last month", "color": "good",   "dc": "up"}},
    {{"val": "4.1",  "label": "Glassdoor",   "delta": "out of 5.0",    "color": "",        "dc": ""}},
    {{"val": "134",  "label": "Open roles",  "delta": "active postings","color": "",        "dc": ""}},
    {{"val": "78%",  "label": "Response rt.","delta": "vs avg",         "color": "",        "dc": "up"}}
  ],
  "signals": [
    {{"type": "bad",  "label": "Layoff history",  "val": "12,000 cuts", "text": "Specific factual finding with dates and numbers."}},
    {{"type": "ok",   "label": "Funding",          "val": "$100B+ cash", "text": "Specific factual finding about financial health."}},
    {{"type": "ok",   "label": "Leadership",        "val": "Stable",      "text": "Specific factual finding about executive stability."}},
    {{"type": "warn", "label": "Hiring velocity",   "val": "Slowing",     "text": "Specific factual finding about current hiring trends."}}
  ],
  "offer_details": null,
  "tips": [
    "Specific tip with <em>key term</em> highlighted.",
    "Specific tip 2 with <em>key term</em> highlighted.",
    "Specific tip 3 with <em>key term</em> highlighted."
  ]
}}

STRICT RULES:
- risk_score MUST be exactly one of: "stable", "caution", "volatile"
- signal type MUST be exactly one of: "ok", "warn", "bad"
- stable = financially healthy, growing, no major concerns (e.g. Stripe, Apple, Nvidia)
- caution = mixed signals, some risk, recent layoffs under 15% of workforce (e.g. Google, Meta, Microsoft)
- volatile = ANY of: filed for bankruptcy, emerged from bankruptcy in last 3 years, laid off >20% of workforce, multiple CEO changes in 2 years, stock down >60%, acquired under distress (e.g. WeWork, Spirit Airlines, Bed Bath Beyond, SVB)

SIGNAL TYPE RULES BY STATUS:
- If stable: signals should be 0 "bad", 0-1 "warn", 3-4 "ok". Truly healthy companies get mostly ok signals.
- If caution: signals should be 1-2 "bad", 1-2 "warn", 0-1 "ok". Mixed picture.
- If volatile: signals should be 2-4 "bad", 0-2 "warn", 0 "ok". Serious problems dominate.
- metrics.val MUST be a real estimated value — never use "—" or placeholder text
- hiring velocity must use REALISTIC varied numbers: e.g. ↓47%, ↑12%, ↓8%, ↑31%, ↓73%
- Glassdoor score must be realistic: 2.1 to 4.6 range, one decimal place
- Open roles should vary widely: 3, 12, 89, 234, 1200, etc.
- metrics.color must be "good", "warn", "danger", or "" (empty string)
- metrics.dc must be "up", "dn", or "" (empty string)
- signals MUST have exactly 4 items with specific real findings about {company}
- tips MUST be specific to {company} and the {stage} stage — not generic advice
- Return ONLY the JSON object, absolutely nothing else"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    raw = response.text.strip()
    raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    raw = raw.strip()

    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        raw = match.group(0)

    data = json.loads(raw)

    if data.get("risk_score") not in ["stable", "caution", "volatile"]:
        data["risk_score"] = "caution"
    for sig in data.get("signals", []):
        if sig.get("type") not in ["ok", "warn", "bad"]:
            sig["type"] = "ok"

    if data.get("signals"):
        store_signals(company, data["signals"], data.get("risk_score", "caution"))

    return data


# ── ROUTES ──

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    body    = request.get_json()
    company = body.get('company', '').strip()
    stage   = body.get('stage', 'applying')
    offer   = body.get('offer', '')

    if not company:
        return jsonify({"error": "Company name required"}), 400

    try:
        result = analyze_company(company, stage, offer)
        return jsonify(result)
    except json.JSONDecodeError as e:
        print(f"JSON error: {e}")
        return jsonify({"error": "Analysis parse failed"}), 500
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/pipeline', methods=['GET'])
def get_pipeline():
    try:
        result = es.search(index=INDEX, body={
            "aggs": {"companies": {"terms": {"field": "company", "size": 50}}},
            "size": 0
        })
        companies = [b["key"] for b in result["aggregations"]["companies"]["buckets"]]
        return jsonify({"companies": companies})
    except Exception as e:
        return jsonify({"companies": [], "error": str(e)})

@app.route('/signals/<company>', methods=['GET'])
def get_signals(company):
    signals = search_signals(company)
    return jsonify({"company": company, "signals": signals, "count": len(signals)})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status":        "ok",
        "service":       "canary",
        "mcp_connected": MCP_CONNECTED,
        "mcp_url":       ES_MCP_URL,
        "elastic":       ES_URL,
        "model":         "gemini-2.5-flash"
    })



@app.route('/comp', methods=['GET'])
def comp():
    role = request.args.get('role', '').strip()
    if not role:
        return jsonify({"error": "Role required"}), 400
    try:
        prompt = """You are a compensation data expert. A job seeker wants market rate data for this role: """ + role + """

Return ONLY valid JSON, no markdown:
{
  "title": "Clean role title (e.g. Senior Product Manager)",
  "cols": ["Level", "Base salary", "Total comp", "Notes"],
  "rows": [
    ["Entry / Junior", "$X – $Y", "$X – $Y", "brief note"],
    ["Mid-level",      "$X – $Y", "$X – $Y", "brief note"],
    ["Senior",         "$X – $Y", "$X – $Y", "brief note"],
    ["Staff / Lead",   "$X – $Y", "$X – $Y", "brief note"],
    ["Director / VP",  "$X – $Y", "$X – $Y", "brief note"]
  ],
  "note": "One sentence about what drives pay variation in this role."
}

Use realistic 2026 US market data from levels.fyi, Glassdoor, Blind for top tech companies.
Adjust levels to fit the role — e.g. for PM use APM/PM/Senior PM/Group PM/Director.
Return ONLY the JSON object."""

        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = response.text.strip()
        import re as _re
        raw = _re.sub(r'^```json\s*', '', raw, flags=_re.MULTILINE)
        raw = _re.sub(r'^```\s*', '', raw, flags=_re.MULTILINE)
        raw = _re.sub(r'\s*```$', '', raw, flags=_re.MULTILINE)
        match = _re.search(r'\{[\s\S]*\}', raw)
        if match: raw = match.group(0)
        return jsonify(json.loads(raw))
    except Exception as e:
        print(f"Comp error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/comp-analyze', methods=['GET'])
def comp_analyze():
    role    = request.args.get('role', '').strip()
    company = request.args.get('company', '').strip()
    base    = request.args.get('base', '').strip()
    equity  = request.args.get('equity', '').strip()
    signing = request.args.get('signing', '').strip()

    if not role or not base:
        return jsonify({"error": "Role and base salary required"}), 400

    try:
        prompt = f"""You are a compensation expert. Analyze this job offer:

Role: {role}
Company: {company if company else "Not specified"}
Base salary: {base}
Equity / RSUs: {equity if equity else "Not provided"}
Signing bonus: {signing if signing else "Not provided"}

Compare against 2026 market rates for this role at top tech companies.

Return ONLY valid JSON, no markdown:
{{
  "verdict": "above",
  "range": "Market range for this role: $X – $Y base",
  "summary": "2-3 sentence assessment of whether this offer is competitive and why.",
  "tips": [
    "Specific negotiation tip 1 based on the numbers",
    "Specific negotiation tip 2",
    "Specific negotiation tip 3"
  ]
}}

verdict must be exactly one of: "above", "at", "below"
Be specific — reference actual numbers from the offer in your summary.
Return ONLY the JSON."""

        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = response.text.strip()
        import re as _re
        raw = _re.sub(r'^```json\s*', '', raw, flags=_re.MULTILINE)
        raw = _re.sub(r'^```\s*', '', raw, flags=_re.MULTILINE)
        raw = _re.sub(r'\s*```$', '', raw, flags=_re.MULTILINE)
        match = _re.search(r'\{{[\s\S]*\}}', raw)
        if match: raw = match.group(0)
        return jsonify(json.loads(raw))
    except Exception as e:
        print(f"Comp analyze error: {e}")
        return jsonify({{"error": str(e)}}), 500

if __name__ == '__main__':
    ensure_index()
    print("\n🐤 Canary is live")
    print(f"   Elastic MCP : {'✅ connected' if MCP_CONNECTED else '⚠️  not connected'}")
    print(f"   MCP URL     : {ES_MCP_URL}")
    print(f"   Elastic     : {ES_URL}")
    print(f"   Model       : gemini-2.5-flash")
    print(f"   UI          : http://localhost:8080\n")
    app.run(host='0.0.0.0', port=8080, debug=False)