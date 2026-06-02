# Realtime Dual-Fetch Hybrid LLM Trust Scorer

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Production_API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Google_Gemini-LLM_Extraction-4285F4?logo=google&logoColor=white)](https://aistudio.google.com)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black?logo=ollama&logoColor=white)](https://ollama.com)
[![Firecrawl](https://img.shields.io/badge/Firecrawl-Web_Scraping-FF4500)](https://firecrawl.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **An end-to-end AI inference microservice that evaluates the trustworthiness of Arabic e-commerce stores in real time.** A URL enters the pipeline — within seconds, a structured 100-point trust score exits. No pre-computation. No cached results. Every analysis is live.

---

## 🧠 What Makes This Different

Most trust/safety tools rely on pre-built static databases or simple heuristics. This pipeline does the opposite: it **fetches, scrapes, extracts, and reasons about a store on-demand**, combining two AI extraction strategies that compensate for each other's weaknesses:

| Strategy | Tool | Extracts |
|---|---|---|
| **Structural Regex** | `re`, `tldextract`, `python-whois` | Phone numbers, VAT IDs, Commercial Registration numbers, domain age |
| **Semantic LLM** | Google Gemini `flash-lite` | Privacy policy existence & Arabic summary, refund policy existence & Arabic summary |

The two branches feed a **5-axis weighted scoring engine** that produces a final score, tier classification, and actionable warnings — all returned as structured JSON from a single API call.

---

## ⚙️ System Architecture

```
POST /api/analyze  ──▶  run_trust_pipeline(url)
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
      WHOIS Lookup      discover_links()    (parallel fetch)
      (domain age)      (policy pages)            │
           │                  │          ┌────────┴────────┐
           │             candidates      │                 │
           │                  │    requests.get()   FirecrawlApp()
           │                  │    (hidden JSON     (clean Markdown)
           │                  └──────────┤
           │                       page_contents{}
           │                  ┌────────┴────────┐
           │            regex_extract()   gemini_extract()
           │            (structural)      (semantic LLM)
           │                  └────────┬────────┘
           └──────────────▶  calculate_trust_score()
                                       │
                              JSON Response ◀── POST /api/chat
                                                 (Ollama chatbot)
```

---

## 🔬 Core ML/AI Components

### 1. Dual-Fetch Scraping Pipeline
For each candidate page, two independent fetches run:
- **Fetch 1 — Raw requests**: Captures hidden `<script>` tag JSON states (React/Next.js hydration data) that Markdown renderers miss
- **Fetch 2 — Firecrawl**: Returns clean, LLM-ready Markdown, stripping nav, ads, and boilerplate

Each fetch feeds a different downstream consumer (Regex ← raw text, Gemini ← clean Markdown), maximizing recall for both strategies.

### 2. Intelligent Link Discovery
Rather than blindly crawling, the pipeline runs a **relevance-ranked candidate URL discovery**:
- Pre-seeds 15 known Arabic/English policy paths (e.g., `/privacy-policy`, `/سياسة-الخصوصية`)
- Parses homepage JSON state for internal links containing policy keywords (Arabic + English)
- Deduplicates and sorts by relevance score, capping at 5 pages

### 3. Regex Extraction Engine (Saudi-Context NLP)
Custom regex patterns built for the Saudi regulatory framework:
```python
PHONE_PATTERN  = r'(?:\+966|00966)[ \-]?(?:5[0-9]{8}|9200[0-9]{5})|05[0-9]{8}'
VAT_PATTERN    = r'\b3[0-9]{14}\b'           # Saudi VAT: 15-digit, starts with 3
CR_PATTERN     = r'\b(?:10|11|20|40|50)[0-9]{8}\b'  # Commercial Registration prefixes
EMAIL_PATTERN  = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
```

### 4. Gemini LLM Semantic Extraction
Sends up to 30,000 characters of clean Markdown per page to `gemini-flash-lite` with a structured JSON prompt. Returns:
```json
{
  "privacy_policy": { "exists": true, "summary": "ملخص السياسة بالعربي" },
  "refund_policy":  { "exists": false, "summary": "" }
}
```

### 5. Multi-Axis Weighted Scoring Engine
Five independent scoring axes combine into a final 0–100 score:

| Axis | Max Points | Signal |
|---|---|---|
| `legal_identity` | 40 | Commercial Registration (CR) + VAT number presence |
| `domain_longevity` | 25 | WHOIS domain age (≥3yr=25, ≥1yr=15, ≥6mo=10) |
| `contactability` | 15 | Phone + Email availability |
| `transparency` | 20 | Privacy & Refund policy detection (10pts each) |
| `penalties` | −40 | "Ghost Syndrome": new domain + no CR + no phone |

**Score → Tier mapping:**
```
≥ 85  →  🟢  Trusted & Secure
≥ 60  →  🟡  Proceed with Caution
 < 60  →  🔴  High Risk / Suspicious
```

Full scoring logic and all 192 scenario combinations documented in [`ANALYZER_SCENARIOS_AR.md`](Final_AI_Server/ANALYZER_SCENARIOS_AR.md).

### 6. Session-Aware Arabic Chatbot (Ollama + Sliding-Window Memory)
The `/api/chat` endpoint powers an Arabic consumer-safety advisor running locally via Ollama (`gemma3:4b`). Each session maintains independent conversation history with a **sliding-window memory manager** — preventing context overflow while preserving relevant chat history.

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | `python --version` |
| Ollama | [Download here](https://ollama.com) — must be running locally |
| Gemini API key | [Get one free at Google AI Studio](https://aistudio.google.com/app/apikey) |
| Firecrawl API key | [Get one at firecrawl.dev](https://www.firecrawl.dev/app/api-keys) |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/Realtime-Dual-Fetch-Hybrid-LLM-Trust-Scorer.git
cd Realtime-Dual-Fetch-Hybrid-LLM-Trust-Scorer/Final_AI_Server

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure API keys
cp ../.env.example .env
# Edit .env and fill in your GEMINI_API_KEY and FIRECRAWL_API_KEY

# 4. Pull the local LLM model (one-time, ~2.5 GB)
ollama pull gemma3:4b

# 5. Start the server
python main.py
```

The server starts on `http://localhost:8000`. Interactive API docs available at `http://localhost:8000/docs`.

---

## 📡 API Reference

### `POST /api/analyze` — Real-Time Trust Evaluation

```bash
curl -X POST http://localhost:8000/api/analyze \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example-store.com"}'
```

**Response:**
```json
{
  "status": "success",
  "url": "https://example-store.com",
  "domain_info": "Domain: example-store.com | Registered: 2019-04-12",
  "extracted_data": {
    "regex_matches": {
      "phone": ["+966512345678"],
      "email": ["INFO@EXAMPLE-STORE.COM"],
      "vat_number": ["310122345600003"],
      "commercial_reg": ["1010123456"]
    },
    "ai_analysis": {
      "privacy_policy": { "exists": true, "summary": "سياسة خصوصية شاملة..." },
      "refund_policy":  { "exists": true, "summary": "يمكن الإرجاع خلال 14 يوم..." }
    }
  },
  "trust_evaluation": {
    "total_score": 100,
    "tier": "Trusted & Secure",
    "color_code": "Green",
    "breakdown": {
      "legal_identity": 40, "domain_longevity": 25,
      "contactability": 15, "transparency": 20, "penalties": 0
    },
    "warnings": [],
    "domain_age_years": 6.1
  }
}
```

### `POST /api/chat` — Arabic Consumer Safety Advisor

```bash
curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user_123", "message": "ما هو السجل التجاري؟"}'
```

**Response:**
```json
{ "reply": "السجل التجاري هو وثيقة رسمية تصدرها وزارة التجارة..." }
```

---

## 🧪 Running the Test Client

A functional test client is included that exercises both endpoints:

```bash
cd Final_AI_Server
python tests/test_client.py
```

This tests chatbot session memory (sliding-window) and runs live analysis on two real stores.

---

## 🗂️ Project Structure

```
Realtime-Dual-Fetch-Hybrid-LLM-Trust-Scorer/
├── .env.example                    ← API key template (copy → .env)
├── .gitignore
├── README.md
│
└── Final_AI_Server/
    ├── main.py                     ← FastAPI app, CORS, CSV logging, endpoints
    ├── config.py                   ← Env var loader (dotenv)
    ├── logger_config.py            ← Structured logging (file + console)
    ├── requirements.txt            ← All dependencies
    ├── ANALYZER_SCENARIOS_AR.md    ← Full scoring logic (Arabic, all 192 scenarios)
    ├── core/
    │   ├── analyzer_engine.py      ← THE PIPELINE: scrape → extract → score
    │   └── chatbot_engine.py       ← ChatbotManager + sliding-window memory
    └── tests/
        └── test_client.py          ← Live integration test client
```

---

## 🛠️ Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **API Server** | FastAPI + Uvicorn | Production ASGI server, CORS, request validation |
| **Scraping** | `requests` + Firecrawl | Dual-fetch: raw HTML & clean Markdown |
| **LLM Inference** | Google Gemini `flash-lite` | Semantic policy extraction |
| **Local LLM** | Ollama `gemma3:4b` | Privacy-preserving Arabic chatbot |
| **OSINT** | `python-whois` + `tldextract` | Domain age verification |
| **HTML Parsing** | BeautifulSoup4 | Hidden script tag extraction |
| **Data Models** | Pydantic | Request/response validation |
| **Logging** | Python `logging` | Structured file + console output |

---

## ⚠️ External Services Required

This project calls three external services. You must provision credentials before running:

| Service | Purpose | How to Get |
|---|---|---|
| **Google Gemini API** | Semantic LLM extraction in the analyzer pipeline | [aistudio.google.com](https://aistudio.google.com/app/apikey) — free tier available |
| **Firecrawl API** | Clean Markdown scraping of store pages | [firecrawl.dev](https://www.firecrawl.dev/app/api-keys) — free tier available |
| **Ollama (local)** | Runs the Arabic chatbot LLM locally on your machine | [ollama.com](https://ollama.com) — free, no API key needed |

Place all credentials in `Final_AI_Server/.env` (copy from `.env.example`).

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
