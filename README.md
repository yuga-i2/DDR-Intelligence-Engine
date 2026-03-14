# DDR Intelligence Engine

> AI-powered building defect diagnostics — upload inspection PDFs, get a professional Defect Diagnostic Report.

Built with LangGraph, LangChain, Groq LLM, and Flask. Submitted for the UrbanRoof AI Engineering assessment.

---

## What It Does

The DDR Intelligence Engine accepts two PDFs — a building inspection report and a thermal imaging report — and runs them through a 5-agent LangGraph pipeline to produce a structured, evidence-grounded Defect Diagnostic Report (DDR) in PDF format.

| Agent | Name | Role |
|-------|------|------|
| 1 | Document Understanding | Extracts text, thermal readings, 29-node spatial graph |
| 2 | Diagnostic Reasoning | Hybrid rules engine + Groq LLM, produces Correlations |
| 3 | Knowledge Retrieval | Treatment protocols, ChromaDB similarity search |
| 4 | Validator | 5 checks, self-correction loop (max 3 iterations) |
| 5 | Report Synthesis | Jinja2 HTML → WeasyPrint PDF |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent orchestration | LangGraph 0.1.19 |
| LLM | Groq — llama-3.1-8b-instant |
| LangChain | langchain 0.2.17, langchain-community 0.2.19 |
| Web UI | Flask 3.0.3 |
| PDF parsing | pdfplumber 0.11.9 |
| PDF generation | WeasyPrint 68.x |
| Vector store | ChromaDB 0.4.x (optional) |
| Graph traversal | NetworkX |
| Runtime | Python 3.13, Windows/Linux/Mac |

---

## Installation

### Prerequisites
- Python 3.13
- A Groq API key (free at https://console.groq.com)

### Setup

\\\ash
git clone https://github.com/yuga-i2/DDR-Intelligence-Engine
cd DDR-Intelligence-Engine
python -m venv .venv
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key_here
\\\

### Install Dependencies

**Windows Python 3.13**:
\\\powershell
pip install -r requirements.txt
\\\

**Mac/Linux**:
\\\ash
pip install -r requirements.txt
\\\

### Run

\\\ash
python app.py
# Open http://localhost:5000
\\\

---

## Usage

1. Open **http://localhost:5000** in your browser
2. Upload your **inspection PDF** and **thermal imaging PDF**
3. Click **Generate DDR**
4. Download the generated **DDR PDF**

---

## Project Structure

\\\
DDR-Intelligence-Engine/
├── app.py                              # Flask web server
├── main.py                             # CLI entrypoint
├── requirements.txt                    # Dependencies
├── .env.example                        # Environment template
├── src/
│   ├── agents/                         # 5 agent modules
│   ├── graph/                          # State machine & workflow
│   ├── knowledge/                      # Rules engine & severity matrix
│   ├── templates/                      # HTML template for PDF
│   └── tools/                          # LLM wrapper, PDF parser, etc.
├── tests/                              # Test suite
└── outputs/                            # Generated PDFs
\\\

---

## Configuration

\\\env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
LOG_LEVEL=INFO
OUTPUT_DIR=outputs
\\\

---

## Design Decisions

- **Hybrid reasoning**: Rules engine (deterministic, 0.82–0.90 confidence) + LLM (ambiguous cases only)
- **Self-correction loop**: Validator routes back to Diagnostic Reasoning (max 3 iterations)
- **Graceful degradation**: Works without ChromaDB, Poppler, Tesseract, or LLM
- **LLM isolation**: All LLM calls route through \src/tools/llm_wrapper.py\ only

---

## License

MIT

---

## Author

Built by Ranan for the UrbanRoof AI Engineering Assessment, March 2026.
