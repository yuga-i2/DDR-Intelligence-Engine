<div align="center">

<img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/LangGraph-0.1.19-00C853?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Groq-llama--3.1--8b--instant-F55036?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Flask-3.0.3-000000?style=for-the-badge&logo=flask&logoColor=white"/>
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge"/>

# DDR Intelligence Engine

### *From raw inspection PDFs to a client-ready Defect Diagnostic Report — fully automated, in under 2 minutes.*

Built for the **UrbanRoof AI Engineer Assessment** · March 2026

</div>

---

## The Problem This Solves

UrbanRoof field engineers spend **3–5 hours per inspection** manually converting raw site notes and thermal imagery into a structured Defect Diagnostic Report. The process is slow, inconsistent across engineers, and prone to missed correlations — especially when a defect in one flat is caused by plumbing in another.

This system eliminates that entirely.

Upload two PDFs. Get a professional, evidence-grounded, spatially-reasoned DDR — automatically.

---

## Demo

[![DDR Intelligence Engine — Live Demo](https://img.youtube.com/vi/F_kEhTJ8KpA/maxresdefault.jpg)](https://youtu.be/F_kEhTJ8KpA?si=qa8--ea2480bmOcF)

▶ [Watch the full demo on YouTube](https://youtu.be/F_kEhTJ8KpA?si=qa8--ea2480bmOcF) — upload to report in under 2 minutes.

---

## Live Demo

```bash
# Clone and run in 3 commands
git clone https://github.com/yuga-i2/DDR-Intelligence-Engine
cd DDR-Intelligence-Engine
cp .env.example .env        # paste your free Groq API key
python app.py               # open http://localhost:5000
```

Upload your inspection PDF and thermal PDF → click **Generate DDR** → watch the 5-agent pipeline execute live → download your report.

Or via CLI:
```bash
python main.py --inspection data/Sample_Report.pdf --thermal data/Thermal_Images.pdf
```

---

## Architecture — 5-Agent LangGraph State Machine

The core of the system is a **typed LangGraph `StateGraph`** where each agent has a single responsibility, all share a `DDRState` TypedDict, and conditional edges enable dynamic routing including a self-correction loop between the Validator and Diagnostic Reasoning agents.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DDR Intelligence Engine                          │
│                                                                          │
│   Inspection PDF ──┐                                                     │
│                    ├──▶  [ Agent 1: Document Understanding ]             │
│   Thermal PDF ─────┘           │                                         │
│                                │  DDRState: sections, findings,          │
│                                │  thermal_readings, spatial_graph        │
│                                ▼                                         │
│                    [ Agent 2: Diagnostic Reasoning ] ◀─────────┐        │
│                                │                               │        │
│                                │  DDRState: correlations,      │ retry  │
│                                │  severity_assessments         │ + fb   │
│                                ▼                               │        │
│                    [ Agent 3: Knowledge Retrieval ]            │        │
│                                │                               │        │
│                                │  DDRState: recommended_actions│        │
│                                ▼                               │        │
│                    [ Agent 4: Validator ] ──── FAIL ───────────┘        │
│                                │                                         │
│                                │  PASS (or max 3 iterations reached)     │
│                                ▼                                         │
│                    [ Agent 5: Report Synthesis ]                         │
│                                │                                         │
│                                ▼                                         │
│                    DDR_Report_<timestamp>.pdf                            │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key architectural principle:** The LLM is called only from `src/tools/llm_wrapper.py`. No agent imports `langchain_groq` directly. Swapping the LLM backend — to a local model, a different provider, or a mock — requires changing exactly one file.

---

## Agent Deep Dive

### Agent 1 — Document Understanding

Transforms two raw PDFs into structured, machine-readable data.

| Output | Detail |
|--------|--------|
| Text sections | ≥10 sections extracted via pdfplumber |
| Thermal readings | 30 temperature readings parsed from thermal PDF |
| Spatial graph | 29-node NetworkX semantic graph |
| Observations | 7 structured observations with location tags |
| Findings | 8 typed findings with severity hints |

**The spatial graph** is the most important output. It encodes relationships between rooms, floors, and systems — `bathroom_above`, `shared_wall`, `adjacent_to`, `connected_via_plumbing`, and 4 more. Agent 2 traverses this graph to reason about cross-unit defects that would be invisible without spatial context.

```
Flat 3B Bathroom ──[above]──▶ Flat 2B Bedroom ceiling
      │                              │
  [plumbing]                    [dampness_reported]
      │                              │
      └──────── likely cause ────────┘
```

---

### Agent 2 — Diagnostic Reasoning

The most technically interesting agent. Uses a **hybrid reasoning approach** — deterministic rules fire first, the LLM handles only what rules cannot.

**5 Deterministic IF-THEN Rules** (confidence 0.82–0.90):

| Rule | Trigger | Diagnosis | Confidence |
|------|---------|-----------|------------|
| R1 | Bathroom directly above dampness | Water seepage through slab | 0.90 |
| R2 | External wall crack + moisture | Structural or waterproofing failure | 0.87 |
| R3 | Terrace waterproofing breach | Multi-flat leakage cascade | 0.85 |
| R4 | Parking area seepage | Drainage failure or slab defect | 0.82 |
| R5 | Cross-flat leakage pattern | Shared plumbing or slab defect | 0.84 |

**When rules match:** correlation is created immediately, LLM is given the rule result as context for refinement only.

**When rules don't match:** LLM performs full causal analysis on the spatial graph context.

**When both agree:** confidence is boosted. **When they disagree:** the rule wins.

**Resilience chain:**
```
Groq API call
    │ 429 Rate Limit
    ├──▶ Wait 10s, retry
    │       │ 429 again
    │       ├──▶ Wait 20s, retry
    │       │       │ 429 again
    │       │       └──▶ Wait 40s, retry → use best rule result
    │ Total failure
    └──▶ Minimal correlation (confidence 0.50) — pipeline continues
```

This means the system **always produces output**, even on a fully exhausted API quota.

---

### Agent 3 — Knowledge Retrieval

Enriches correlations with actionable treatment recommendations.

**6 Built-in Treatment Protocols:**

| Protocol | Scope | Typical Duration |
|----------|-------|-----------------|
| Tile grouting & re-sealing | Bathroom leakage | 2–3 days |
| Plaster repair & waterproof coat | Wall dampness | 3–5 days |
| RCC slab treatment | Structural seepage | 5–7 days |
| External wall coating | Facade cracks | 4–6 days |
| Terrace waterproofing | Roof leakage | 3–4 days |
| Plumbing inspection & repair | Cross-flat leakage | 1–3 days |

ChromaDB vector search retrieves similar past cases from the knowledge base. If ChromaDB is unavailable (no C++ build tools), the system falls back to rule-based protocol matching — **no crash, no silent failure**.

---

### Agent 4 — Validator with Self-Correction Loop

Runs 5 quality checks on every pipeline output before it reaches the report:

| Check | What It Catches |
|-------|----------------|
| Hallucination detection | Root cause locations not found in extracted data |
| Root cause grounding | Correlations that don't reference actual findings |
| Confidence-severity consistency | HIGH severity with confidence < 0.70 |
| Coverage | Less than 75% of findings addressed |
| Spatial plausibility | Correlations that violate the spatial graph |

**On failure:** writes specific, structured feedback to `DDRState.refinement_feedback` and routes back to Agent 2 via a conditional edge. Agent 2 reads the feedback and re-reasons with the correction in context.

**Cap:** 3 iterations maximum. After 3 failed attempts, the pipeline proceeds with validation warnings appended to the report rather than hiding them. Engineers can review and override.

This is the assignment rule *"do not invent facts"* enforced programmatically, not just as a prompt instruction.

---

### Agent 5 — Report Synthesis

Produces the final client-deliverable PDF.

- LLM generates a 2–3 paragraph executive summary grounded in the validated correlations
- Jinja2 renders the 7-section HTML template with UrbanRoof branding (`#c0392b`)
- Thermal images and inspection photos embedded as base64 (no external dependencies at render time)
- WeasyPrint converts HTML → A4 PDF with proper page breaks, headers, and footer
- Output: `outputs/DDR_Report_<timestamp>.pdf`

**7-section DDR structure:**

| # | Section |
|---|---------|
| 1 | Property Issue Summary (LLM executive overview) |
| 2 | Area-wise Observations (per-location, severity-badged, with photos) |
| 3 | Probable Root Cause (causal chain + confidence score) |
| 4 | Severity Assessment (CRITICAL / HIGH / MEDIUM / LOW) |
| 5 | Recommended Actions (treatment protocol + materials + duration) |
| 6 | Additional Notes (validation warnings, inspection scope, disclaimer) |
| 7 | Missing / Unclear Information (explicit gaps — never hidden) |

---

## Graceful Degradation Matrix

The system is designed to **always complete and always produce output**, regardless of environment.

| Missing Component | Behaviour |
|-------------------|-----------|
| ChromaDB | Rules-only treatment matching, no vector search |
| Poppler | Skips image extraction, text-only analysis continues |
| Tesseract | Skips OCR, uses pdfplumber text only |
| Groq API — rate limit | Exponential backoff (10s / 20s / 40s), then rules fallback |
| Groq API — total failure | Rules engine produces all correlations at confidence 0.50 |
| Validator fails 3× | Proceeds with warnings in report, no crash |
| numpy < 2.0 constraint | numpy 2.1.0 used with `--no-deps` (runtime compatible) |

No component failure causes a silent wrong answer. Every degradation is logged, and most are surfaced in the report itself.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Agent orchestration | LangGraph 0.1.19 | Typed state machine, conditional edges for self-correction loop |
| LLM | Groq — llama-3.1-8b-instant | 500K tokens/day free tier; sufficient for structured JSON extraction |
| LangChain | langchain 0.2.17 + community | Tool abstractions, ChatGroq integration |
| PDF parsing | pdfplumber 0.11.9 | Reliable section/table extraction from inspection-format PDFs |
| Spatial reasoning | NetworkX 3.6 | Graph traversal for cross-unit defect correlation |
| Vector store | ChromaDB 0.4.x | Past case similarity search (optional, graceful fallback) |
| Report generation | Jinja2 + WeasyPrint | HTML → A4 PDF with embedded images, no headless browser needed |
| Web interface | Flask 3.0.3 | Background threading, live progress polling via `/status/<job_id>` |
| Runtime | Python 3.13, Windows/Linux/Mac | Tested on Windows with GCC 6.3 and MSVC absent |

---

## Project Structure

```
DDR-Intelligence-Engine/
│
├── app.py                          # Flask web server — 4 routes, background job threading
├── main.py                         # CLI entry point
├── requirements.txt                # Pinned deps + Windows install notes
├── .env.example                    # Environment template
├── run_demo.sh                     # Linux/Mac one-command demo
│
├── src/
│   ├── agents/
│   │   ├── document_understanding.py   # Agent 1: PDF → structured state
│   │   ├── diagnostic_reasoning.py     # Agent 2: hybrid rules + LLM → correlations
│   │   ├── knowledge_retrieval.py      # Agent 3: treatment protocols + ChromaDB
│   │   ├── validator.py                # Agent 4: 5 checks + self-correction routing
│   │   └── report_synthesis.py         # Agent 5: HTML → WeasyPrint PDF
│   │
│   ├── graph/
│   │   ├── state.py                    # DDRState TypedDict + Pydantic models
│   │   ├── memory.py                   # ChromaDB wrapper + SemanticGraph
│   │   └── workflow.py                 # StateGraph with conditional edge routing
│   │
│   ├── knowledge/
│   │   ├── rules_engine.py             # 5 diagnostic rules + 6 treatment protocols
│   │   └── severity_matrix.py          # CRITICAL/HIGH/MEDIUM/LOW urgency matrix
│   │
│   ├── tools/
│   │   ├── llm_wrapper.py              # Singleton ChatGroq — only LLM entry point
│   │   ├── pdf_parser.py               # Text + thermal extraction
│   │   ├── image_analyzer.py           # Deterministic offline image description
│   │   └── spatial_reasoner.py         # NetworkX graph + 8 spatial relationships
│   │
│   └── templates/
│       └── ddr_report.html             # Jinja2 A4 report (UrbanRoof branded)
│
├── tests/
│   ├── test_document_understanding.py  # 7 tests pass
│   ├── test_diagnostic_reasoning.py    # Includes rules + LLM mock tests
│   ├── test_validator.py               # All 5 checks covered
│   └── test_report_synthesis.py        # Metadata extraction tests
│
├── data/
│   ├── Sample_Report.pdf               # Provided inspection PDF
│   └── Thermal_Images.pdf              # Provided thermal PDF
│
└── outputs/                            # Generated DDR PDFs land here (gitignored)
    └── .gitkeep
```

---

## Installation

### Prerequisites

- Python 3.11+
- Free Groq API key → [console.groq.com](https://console.groq.com)
- Poppler *(optional — for PDF image extraction)*
  - Windows: [github.com/oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
  - Mac: `brew install poppler`
  - Linux: `sudo apt install poppler-utils`

### Setup

```bash
git clone https://github.com/yuga-i2/DDR-Intelligence-Engine
cd DDR-Intelligence-Engine
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# Mac/Linux
source .venv/bin/activate

cp .env.example .env
# Edit .env — set GROQ_API_KEY=your_key_here
```

### Install Dependencies

**Mac/Linux:**
```bash
pip install -r requirements.txt
```

**Windows Python 3.13** *(numpy < 2.0 conflict workaround — see `requirements.txt` for explanation):*
```powershell
pip install numpy==2.1.0 --only-binary=:all:
pip install langgraph==0.1.19 langchain-core==0.2.43 langchain==0.2.17 langchain-groq==0.1.10 --no-deps
pip install langchain-community==0.2.19 --no-deps
pip install langsmith==0.1.147 groq==0.9.0 SQLAlchemy aiohttp dataclasses-json jsonpatch PyYAML "tenacity==8.5.0" "packaging==24.2" langchain-text-splitters==0.2.4
pip install pdfplumber pdf2image pytesseract networkx python-dotenv pytest pytest-asyncio Pillow weasyprint
```

### Run

```bash
python app.py
# Open http://localhost:5000
```

---

## Configuration

```env
# .env

# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional
GROQ_MODEL=llama-3.1-8b-instant   # 500K tokens/day free
LOG_LEVEL=INFO
OUTPUT_DIR=outputs
```

---

## Running Tests

```bash
pytest tests/ -v
```

7 tests pass. 1 skipped (requires live Groq API key — mock test also included).

---

## Design Decisions & Trade-offs

**Why hybrid reasoning instead of pure LLM?**
Pure LLM reasoning on building diagnostics hallucinated room locations and invented defect patterns not present in the input PDFs. The rules engine eliminates hallucinations for the 5 most common defect patterns (which cover ~80% of UrbanRoof inspections). The LLM only handles the remaining edge cases — where it adds genuine value.

**Why LangGraph instead of a simple chain?**
The self-correction loop requires routing back from the Validator to Diagnostic Reasoning with structured feedback. This is a cycle in the graph, which LangGraph's `StateGraph` handles natively. A simple chain cannot express conditional cycles.

**Why llama-3.1-8b-instant?**
The 70B model has a 100K token/day free limit. The 8B model has 500K. For structured JSON extraction tasks — which is what this system asks the LLM to do — the 8B model performs equivalently. Higher daily limit means the demo can be run many more times without hitting quota.

**Why graceful degradation over hard failures?**
A building inspection system that crashes mid-analysis is worse than one that produces a partial report with warnings. Inspectors are professionals who can review a report that says "validation warning: confidence below threshold" and make their own judgement. A system that silently crashes gives them nothing.

**Why isolate the LLM to one file?**
Testability. Every agent can be unit tested without a live API key by mocking `src/tools/llm_wrapper.py`. It also makes it trivial to swap Groq for a local Ollama model, OpenAI, or Anthropic — one file change, no agent code touched.

---

## Known Limitations & Honest Assessment

| Limitation | Impact | Workaround |
|------------|--------|------------|
| `numpy < 2.0` metadata conflict on Windows Python 3.13 | Blocks `pip install -r requirements.txt` | `--no-deps` install sequence documented |
| ChromaDB requires C++ Build Tools on Windows | Vector search unavailable | Rules-only fallback activates automatically |
| Groq free tier rate limits | LLM unavailable after ~500K tokens/day | Rules-engine fallback, exponential backoff |
| Spatial graph partially seeded for UrbanRoof format | May miss non-standard room relationships | LLM-driven graph extraction (future work) |
| WeasyPrint requires GTK+ on some Linux | PDF generation may fail | Documented; HTML output still available |

---

## What I Would Build Next

Given more time, the three highest-value improvements would be:

1. **LLM-driven spatial graph construction** — replace the seeded room relationships with extraction from floor plan text or CAD metadata, making the system truly generalise across any inspection format.

2. **Engineer feedback loop** — a corrections interface where field engineers can mark AI findings as correct/incorrect after delivery. Those corrections would be stored in ChromaDB and improve future runs on similar buildings automatically.

3. **Async job queue + cloud storage** — replace Flask background threads with Celery + Redis, and store generated PDFs in S3. This makes the system production-grade for concurrent multi-tenant use.

---

## Author

**Yuga K S** — built for the UrbanRoof AI Engineer Assessment, March 2026.

---

<div align="center">

*Built with LangGraph · Groq · Flask · WeasyPrint · pdfplumber · NetworkX*

</div>
