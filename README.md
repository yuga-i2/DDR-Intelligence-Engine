# DDR Intelligence Engine

> AI-powered multi-agent system that reads building inspection PDFs and generates professional Defect Diagnostic Reports (DDRs) — built for the UrbanRoof AI Engineer assignment.

---

## Live Demo

```bash
pip install -r requirements.txt
cp .env.example .env        # add your GROQ_API_KEY (free at console.groq.com)
python app.py               # open http://localhost:5000
```

Upload inspection PDF + thermal PDF → click Generate → DDR downloads automatically.

Or via CLI:
```bash
python main.py --inspection data/Sample_Report.pdf --thermal data/Thermal_Images.pdf
```

---

## What It Does

UrbanRoof field engineers collect raw inspection data and thermal imagery on-site. Converting that into a structured, client-ready Defect Diagnostic Report currently requires hours of manual analysis. This system automates the entire pipeline end-to-end.

The system reads two PDFs, extracts observations and thermal readings, builds a spatial relationship graph of the building, reasons about root causes using a hybrid rules + LLM approach, validates its own output through a self-correction loop, and produces a professional 7-section PDF report ready for client delivery — all in under 2 minutes.

It is designed to generalise across UrbanRoof-format inspection documents, not just the provided sample files.

---

## System Architecture

Five specialised agents connected as a LangGraph state machine. Each agent has a single responsibility. All agents communicate through a typed shared state (`DDRState`). The LLM is called only from `src/tools/llm_wrapper.py` — no agent imports langchain_groq directly.

```
PDF Inputs (Inspection Report + Thermal Report)
                    │
                    ▼
    ┌───────────────────────────────────┐
    │   1. Document Understanding Agent  │
    │                                   │
    │   • pdfplumber section extraction │
    │   • Thermal metadata parsing      │
    │   • NetworkX semantic graph       │
    │     (29 nodes, 15 spatial edges)  │
    │   • 7 Observations extracted      │
    │   • 8 Findings extracted          │
    └────────────────┬──────────────────┘
                     │
                     ▼
    ┌───────────────────────────────────┐
    │   2. Diagnostic Reasoning Agent    │
    │                                   │
    │   • Spatial graph traversal       │
    │     (rooms above / adjacent)      │
    │   • 5 deterministic IF-THEN rules │
    │     (confidence 0.82 – 0.90)      │
    │   • Groq LLM causal analysis      │
    │   • Rule-LLM confidence merge     │
    │   • Rules-only fallback when      │
    │     LLM is unavailable            │
    └────────────────┬──────────────────┘
                     │
                     ▼
    ┌───────────────────────────────────┐
    │   3. Knowledge Retrieval Agent     │
    │                                   │
    │   • 6 treatment protocols         │
    │   • ChromaDB past-case search     │
    │   • Treatment deduplication       │
    └────────────────┬──────────────────┘
                     │
                     ▼
    ┌───────────────────────────────────┐       ┌─────────────────────┐
    │   4. Validator Agent               │─FAIL─▶│  Diagnostic         │
    │                                   │       │  Reasoning Agent    │
    │   5 quality checks:               │◀──────│  (retry with        │
    │   • Hallucination detection        │       │   specific feedback)│
    │   • Root cause grounding          │       └─────────────────────┘
    │   • Confidence-severity match     │         max 3 iterations
    │   • Coverage ≥ 75%                │
    │   • Spatial plausibility          │
    └────────────────┬──────────────────┘
                     │ PASS
                     ▼
    ┌───────────────────────────────────┐
    │   5. Report Synthesis Agent        │
    │                                   │
    │   • LLM executive summary         │
    │   • Jinja2 HTML template          │
    │   • WeasyPrint → A4 PDF           │
    │   • Base64 image embedding        │
    │   • UrbanRoof branded layout      │
    └────────────────┬──────────────────┘
                     │
                     ▼
            DDR_Report_<timestamp>.pdf
```

---

## DDR Output: 7 Sections

| # | Section | Content |
|---|---|---|
| 1 | Property Issue Summary | LLM-generated executive overview |
| 2 | Area-wise Observations | Per-location symptoms + severity badge + embedded photographs + thermal images |
| 3 | Probable Root Cause | Causal chain per area with confidence score |
| 4 | Severity Assessment | CRITICAL / HIGH / MEDIUM / LOW sorted by urgency |
| 5 | Recommended Actions | Treatment protocols with materials list + duration |
| 6 | Additional Notes | Validation warnings, inspection scope, disclaimer |
| 7 | Missing / Unclear Information | Explicit "Not Available" for every data gap |

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent orchestration | LangGraph (typed state machine, conditional edges) |
| LLM inference | Groq API — `llama-3.1-8b-instant` |
| PDF parsing | pdfplumber + pdf2image |
| Spatial reasoning | NetworkX semantic graph |
| Deterministic rules | Custom Python rules engine (5 diagnostic rules) |
| Treatment knowledge | 6 protocol definitions (tile, plaster, RCC, terrace, coating, plumbing) |
| Vector memory | ChromaDB (past case similarity search) |
| Report generation | Jinja2 + WeasyPrint (A4 PDF) |
| Web interface | Flask (upload UI, background jobs, live progress) |
| Testing | pytest — 18+ tests across all agents |

---

## Key Design Decisions

**1. Hybrid reasoning — rules first, LLM second**
A deterministic rules engine fires before any LLM call. Rules encode known building diagnostics patterns with confidence 0.82–0.90. The LLM handles ambiguous cases only. When rules and LLM agree, confidence is boosted. When they disagree, the rule wins. This makes the system reliable even when the LLM underperforms.

**2. Self-correction loop**
The Validator runs 5 checks on every output. On failure it writes specific feedback to state and routes back to Diagnostic Reasoning (max 3 iterations). The report explicitly flags unresolved issues rather than hiding them.

**3. LLM isolation**
All Groq API calls go through `src/tools/llm_wrapper.py` only. No agent imports `langchain_groq` directly. The LLM can be swapped, mocked, or replaced with a local model by changing one file.

**4. Graceful degradation**
The pipeline completes without ChromaDB (rules-only mode), without poppler (skips image extraction), and without LLM access (rules-engine fallback produces correlations for all observations). Nothing crashes silently.

**5. Evidence-grounded output**
Every correlation must be grounded to an extracted finding. The Validator rejects any root cause location that cannot be found in the extracted data. Enforces the assignment rule: do not invent facts.

---

## Project Structure

```
DDR-Intelligence-Engine/
├── app.py                        # Flask web UI
├── main.py                       # CLI entry point
├── requirements.txt
├── .env.example
├── run_demo.sh
├── data/                         # Input PDFs (committed)
│   ├── Sample_Report.pdf
│   └── Thermal_Images.pdf
├── outputs/                      # Generated reports land here
├── src/
│   ├── agents/
│   │   ├── document_understanding.py
│   │   ├── diagnostic_reasoning.py
│   │   ├── knowledge_retrieval.py
│   │   ├── validator.py
│   │   └── report_synthesis.py
│   ├── graph/
│   │   ├── state.py              # DDRState TypedDict + Pydantic models
│   │   ├── memory.py             # ChromaDB + SemanticGraph
│   │   └── workflow.py           # LangGraph state machine
│   ├── knowledge/
│   │   ├── rules_engine.py       # 5 diagnostic rules + 6 treatment protocols
│   │   └── severity_matrix.py    # CRITICAL/HIGH/MEDIUM/LOW matrix
│   ├── tools/
│   │   ├── llm_wrapper.py        # Only file that calls the LLM
│   │   ├── pdf_parser.py
│   │   ├── image_analyzer.py
│   │   └── spatial_reasoner.py
│   └── templates/
│       └── ddr_report.html       # Jinja2 A4 template
└── tests/
    ├── test_document_understanding.py
    ├── test_diagnostic_reasoning.py
    ├── test_validator.py
    └── test_report_synthesis.py
```

---

## Quickstart (Full Setup)

### Prerequisites
- Python 3.11+
- Groq API key — free at [console.groq.com](https://console.groq.com)
- poppler-utils — for PDF image extraction (Linux: `apt install poppler-utils`)
- WeasyPrint system libs — for PDF generation (Linux: `apt install libpango-1.0-0 libpangoft2-1.0-0`)

### Install
```bash
git clone https://github.com/yuga-i2/DDR-Intelligence-Engine
cd DDR-Intelligence-Engine
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key_here
```

### Run web UI
```bash
python app.py
# Open http://localhost:5000
```

### Run CLI
```bash
python main.py --inspection data/Sample_Report.pdf --thermal data/Thermal_Images.pdf
# PDF appears in outputs/
```

### Run tests
```bash
python -m pytest tests/ -v
```

---

## Limitations

- WeasyPrint requires GTK+ system libraries — Linux/WSL2 recommended for PDF generation
- poppler required for image extraction — without it the pipeline continues but embeds no photos
- Groq free tier has daily token limits — `llama-3.1-8b-instant` is used by default for maximum throughput; system falls back to rules-only if quota is exceeded
- Spatial graph relationships are partially seeded for UrbanRoof document format — full generalisation via LLM-driven extraction is the next improvement

---

## How I Would Improve It

- **Dynamic spatial graph** — replace seeded room relationships with LLM-driven extraction from floor plan text or CAD data
- **Engineer feedback loop** — let field engineers correct AI findings post-delivery; corrections improve future runs
- **OCR fallback** — pytesseract for scanned or image-only PDFs
- **Domain embeddings** — fine-tune embeddings on historical UrbanRoof inspection data for better ChromaDB similarity
- **Cloud deployment** — Celery + Redis async job queue, S3 for PDF storage, multi-tenant REST API
