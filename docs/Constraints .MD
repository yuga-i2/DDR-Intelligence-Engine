# DDR Intelligence Engine — Project Constraints

> **Purpose:** These constraints govern every file, folder, and commit in this repository.
> They exist to keep the codebase clean, the directory readable at a glance, and the
> repository professional when pushed to GitHub. Copilot and all contributors must follow
> these rules without exception.

---

## File Creation Rules

**Never create a file unless it has a clear, single responsibility.**
Every file must do one thing. A file that does two unrelated things must be split into two files.

**Never create a file speculatively.**
Do not create placeholder files, stub files, or "we might need this later" files.
If a module is not needed for the current working feature, do not create it.

**Never create temporary files in the project root or src/.**
All scratch work, debug outputs, and temporary files belong in a directory that is gitignored.
Use the `outputs/` directory for generated artifacts and `data/` for input files.
Neither of these directories belongs in the repository.

**Never create markdown files anywhere except the project root.**
The only permitted markdown files in this repository are:
- `PROJECT_REFERENCE.md` — in the project root
- `CONSTRAINTS.md` — in the project root
- `README.md` — in the project root

No markdown files inside `src/`, `tests/`, `notebooks/`, or any subdirectory.
No NOTES.md, TODO.md, PLAN.md, ARCHITECTURE.md, AGENTS.md, or any variant.
If documentation is needed for a module, it belongs in the module's docstring — not in a separate file.

---

## Naming Rules

**All Python files use snake_case. No exceptions.**
Correct: `document_understanding.py`, `rules_engine.py`, `ddr_report.html`
Wrong: `DocumentUnderstanding.py`, `RulesEngine.py`, `DDRReport.html`

**All file names must describe function, not phase or sequence.**
Wrong: `agent1.py`, `phase2_reasoning.py`, `step3_validate.py`, `v2_synthesis.py`
Correct: `diagnostic_reasoning.py`, `validator.py`, `report_synthesis.py`

**No version suffixes in file names.**
Wrong: `workflow_v2.py`, `state_final.py`, `template_new.html`
The version control system handles versioning. File names do not.

**No date suffixes in file names.**
Wrong: `main_2024_01_15.py`, `state_jan.py`

**Directories use lowercase kebab-case or single words only.**
Correct: `src/`, `tests/`, `notebooks/`, `outputs/`
Wrong: `Source_Files/`, `MyAgents/`, `Test Scripts/`

---

## Directory Structure Rules

**The top-level directory must stay flat.**
Only these items belong at the project root:
- `src/` directory
- `tests/` directory
- `notebooks/` directory
- `outputs/` directory (gitignored)
- `data/` directory (gitignored)
- `main.py`
- `requirements.txt`
- `.env` (gitignored)
- `.env.example`
- `.gitignore`
- `PROJECT_REFERENCE.md`
- `CONSTRAINTS.md`
- `README.md`

Nothing else. No loose Python scripts. No loose config files. No extra folders.

**The `src/` directory has exactly four subdirectories.**
- `agents/` — one file per agent, nothing else
- `graph/` — state, workflow, memory only
- `tools/` — pdf_parser, image_analyzer, spatial_reasoner only
- `knowledge/` — rules_engine, severity_matrix only
- `templates/` — ddr_report.html only

No new subdirectories inside `src/` without updating this constraints file first.

**The `tests/` directory contains only test files.**
Every test file is named `test_{module_name}.py` matching the module it tests.
No conftest.py unless pytest fixtures are shared across three or more test files.
No test data files inside `tests/`. Test data lives in `data/test_fixtures/` which is gitignored.

---

## Git and GitHub Rules

**The `.gitignore` must include all of the following before the first commit:**
```
.env
outputs/
data/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.DS_Store
*.egg-info/
dist/
build/
.venv/
venv/
*.log
chroma_db/
*.pdf
!.env.example
```

**Never commit generated files.**
PDFs, images, extracted text files, ChromaDB persistence files — none of these belong in the repository.

**Never commit `.env`.**
The `.env.example` file is committed. The `.env` file is never committed.

**Commit messages describe what changed and why, not how.**
Wrong: `fixed the json parsing in agent 2`
Correct: `handle LLM JSON parse failure in diagnostic_reasoning with single retry`

---

## Code Quality Rules

**Every function must have a docstring.**
Single-line for simple utilities. Multi-line for agents and complex functions.
The docstring states what the function does, what it takes, and what it returns.

**Every agent function signature is strictly typed.**
```python
def document_understanding_agent(state: DDRState) -> DDRState:
```
No untyped functions in `src/agents/`. No functions that accept `**kwargs` in agent files.

**No magic strings in agent files.**
Field names, severity levels, relationship types, and node types must be defined as constants
in `src/graph/state.py` and imported. No string literals like `"above"` or `"high"` scattered
through agent files.

**No print statements in production code.**
All logging uses the Python `logging` module with the logger named after the module.
```python
import logging
logger = logging.getLogger(__name__)
```
`print()` is only permitted inside `notebooks/`.

**No bare `except` clauses.**
Every try-except must catch a specific exception type. `except Exception as e` is acceptable
as a catch-all only when the error is logged with `logger.error(e, exc_info=True)`.

**LLM calls are never made directly in agent files.**
All LLM calls go through wrapper functions defined in `src/tools/` or `src/graph/`.
Agents import and call these wrappers. This makes mocking for tests straightforward.

---

## Dependency Rules

**`requirements.txt` is the only dependency file.**
No `pyproject.toml`, no `setup.py`, no `Pipfile` unless the project explicitly migrates to one of these. Not both.

**Pin major versions for core dependencies.**
```
langgraph>=0.1.0,<0.2.0
langchain-groq>=0.1.0,<0.2.0
chromadb>=0.4.0,<0.5.0
```
Unpinned dependencies produce unreproducible builds.

**Do not add a dependency for something the standard library handles.**
No `requests` when `httpx` (already a langchain dependency) works.
No `python-dotenv` unless environment loading is already being done with it.
No utility libraries for one-liner operations.

---

## Notebook Rules

**`notebooks/` contains exactly one notebook: `system_demo.ipynb`.**
No exploratory notebooks, no debug notebooks, no scratch notebooks committed to the repository.
Exploratory work is done locally and discarded.

**The demo notebook must be clean before commit.**
All cell outputs must be cleared. No notebooks with executed outputs committed.
Exception: the final demo notebook prepared for presentation may have outputs.

---

## Environment Rules

**All configuration is via environment variables loaded from `.env`.**
No hardcoded file paths. No hardcoded model names. No hardcoded API keys anywhere in source.
All paths are constructed using `os.path.join` and a base directory from environment.

**The system must run with a single command after environment setup.**
```
python main.py --inspection data/inspection_report.pdf --thermal data/thermal_report.pdf
```
No multi-step manual setup. No "first run this, then run that." The README documents exactly
one command to install dependencies and one command to run the system.

---

## What Is Strictly Prohibited

- Creating any file outside the defined directory structure without updating this file first
- Creating markdown documentation files anywhere except the project root
- Committing any PDF, image, or generated output file
- Committing `.env` or any file containing API keys
- Naming files after sequence, phase, version, or date
- Using print statements in any file outside notebooks/
- Writing LLM calls directly inside agent functions
- Creating subdirectories inside `src/` without updating this file first
- Leaving TODO comments in committed code (use GitHub Issues instead)
- Creating requirements files that are not `requirements.txt`