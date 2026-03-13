# DDR Intelligence Engine — Complete Project Reference

> **Purpose:** This file is the single source of truth for VS Code Copilot and all contributors.
> Every architectural decision, agent behavior, prompt pattern, LangGraph implementation detail,
> and quality standard is documented here. Read this before touching any file in the project.

---

## What This Project Is

The DDR Intelligence Engine is a multi-agent AI system that reads a building inspection PDF and a thermal imaging PDF, reasons about the data the way a senior structural diagnostics consultant would, and produces a polished Defect Diagnostic Report (DDR) PDF. It does not simply extract and reformat — it reasons spatially, applies expert domain rules, validates its own output, self-corrects when it finds errors, and synthesizes a professional client-ready report with images and recommendations.

The system is built on LangGraph as its orchestration backbone, uses Groq-hosted LLMs for fast and free inference, stores intermediate reasoning in a semantic graph built with NetworkX, and retrieves domain knowledge from a ChromaDB vector store. The final output is rendered from a Jinja2 HTML template and converted to PDF using WeasyPrint.

---

## Core Philosophy

Every design decision must answer yes to three questions:

1. Does this make the output more accurate and grounded in the source document?
2. Does this make the system more observable, debuggable, and maintainable?
3. Does this demonstrate production-grade AI system design, not a simple chain of LLM calls?

The system thinks in graphs, validates against facts, and writes like a consultant.

---

## System Architecture Overview

The system is a LangGraph state machine with five specialized agents that share a single typed state object. Data flows forward through the pipeline. When the validator detects hallucinations or logical inconsistencies, it injects structured feedback into the state and the graph loops back to the diagnostic reasoning agent for a corrected pass. This loop runs a maximum of three times before the system proceeds with warnings attached.

```
Input PDFs
    ↓
Document Understanding Agent      ← reads, extracts, builds semantic graph
    ↓
Diagnostic Reasoning Agent        ← connects symptoms to root causes spatially
    ↓
Knowledge Retrieval Agent         ← applies expert rules + vector similarity
    ↓
Validator Agent                   ← checks every claim against source facts
    ↓ (if hallucinations found, loops back to Diagnostic Reasoning with feedback)
Report Synthesis Agent            ← renders HTML template → PDF
    ↓
Output: generated_ddr.pdf
```

All agents read from and write to one shared DDRState object. A shared memory layer (semantic graph + vector store) is accessible to all agents throughout the run.

---

## Technology Stack and Why Each Was Chosen

| Component | Library | Reason |
|---|---|---|
| Agent orchestration | langgraph | State machine with conditional edges; supports cycles for self-correction |
| LLM inference | langchain-groq | Free tier, fast, runs Llama 3 which is strong for structured extraction |
| Structured output | Pydantic v2 | All LLM outputs are validated models, not raw dicts |
| Semantic graph | networkx | Lightweight, pure Python, sufficient for room-relationship graphs |
| Vector store | chromadb | Local, no server needed, fast enough for small KB |
| PDF extraction | pdfplumber | Better than PyPDF2 for tables and layout-aware text |
| Image extraction | pdf2image + Pillow | Converts PDF pages to images cleanly |
| OCR fallback | pytesseract | Only used when pdfplumber misses text in image-heavy pages |
| Template engine | jinja2 | Clean separation of logic and presentation |
| HTML to PDF | weasyprint | Supports CSS properly; produces print-quality PDFs |
| Testing | pytest | Standard; all agents are independently testable |

---

## Project Directory Structure

Every file and folder has a deliberate name that reflects its function. No ambiguity.

```
ddr-intelligence-engine/
│
├── src/
│   ├── agents/
│   │   ├── document_understanding.py
│   │   ├── diagnostic_reasoning.py
│   │   ├── knowledge_retrieval.py
│   │   ├── validator.py
│   │   └── report_synthesis.py
│   │
│   ├── graph/
│   │   ├── state.py               ← DDRState TypedDict + all Pydantic models
│   │   ├── workflow.py            ← LangGraph graph definition and compilation
│   │   └── memory.py             ← SemanticGraph class + ChromaDB wrapper
│   │
│   ├── tools/
│   │   ├── pdf_parser.py          ← pdfplumber + pdf2image extraction utilities
│   │   ├── image_analyzer.py      ← image reading, captioning, evidence tagging
│   │   └── spatial_reasoner.py    ← graph traversal helpers (get_rooms_above, etc.)
│   │
│   ├── knowledge/
│   │   ├── rules_engine.py        ← expert IF-THEN rules for building diagnostics
│   │   └── severity_matrix.py     ← symptom × location × extent → severity level
│   │
│   └── templates/
│       └── ddr_report.html        ← Jinja2 HTML template for final DDR output
│
├── outputs/                       ← generated_ddr.pdf lands here; gitignored
├── tests/
│   ├── test_document_understanding.py
│   ├── test_diagnostic_reasoning.py
│   ├── test_validator.py
│   └── test_workflow_integration.py
│
├── notebooks/
│   └── system_demo.ipynb
│
├── main.py                        ← entry point; accepts PDF paths as CLI args
├── requirements.txt
├── .env.example
├── .gitignore
├── PROJECT_REFERENCE.md           ← this file
└── CONSTRAINTS.md
```

---

## State Schema — The Central Nervous System

The state is the single object that flows through every agent. It is defined as a TypedDict so LangGraph can track it. All nested objects are Pydantic BaseModel classes so every LLM output is validated before it enters the state.

### Pydantic Models

**ImageEvidence**
Represents one image extracted from a PDF. Fields: `image_path` (str), `location` (str — the room or area this image belongs to), `image_type` (str — "thermal" or "visual"), `description` (str — what the image shows), `metadata` (Dict — page number, dimensions, bounding box).

**Observation**
Represents one symptom found on the negative side of the inspection report. Fields: `location` (str), `symptom` (str), `severity` (Literal["low", "medium", "high"]), `extent` (str — percentage or area description), `evidence` (List[ImageEvidence]).

**Finding**
Represents one cause found on the positive side. Fields: `location` (str), `defect_type` (str), `description` (str), `extent` (str).

**Correlation**
Represents a validated causal link between a symptom and a root cause. Fields: `symptom_location` (str), `symptom_type` (str), `root_cause_location` (str), `root_cause_type` (str), `confidence` (float 0–1), `reasoning` (str), `supporting_evidence` (List[str] — references to actual text from the source).

**SemanticGraph**
Wraps a NetworkX DiGraph. Nodes represent rooms and structural elements. Edges represent relationships: `above`, `below`, `adjacent_to`, `causes`, `has_symptom`, `has_finding`. This graph enables spatial traversal — given "Hall ceiling", the system can query what room sits above it and what defects that room has.

### DDRState TypedDict

```
inspection_pdf_path: str
thermal_pdf_path: str
extracted_text: Dict[str, Any]          ← structured output from pdfplumber
extracted_images: List[ImageEvidence]   ← all images with location tags
extracted_tables: List[Dict]            ← any tabular data in the PDFs
semantic_graph: SemanticGraph           ← networkx graph of building structure
observations: List[Observation]         ← symptoms (negative side)
findings: List[Finding]                 ← causes (positive side)
correlations: List[Correlation]         ← symptom → root cause links
root_causes: List[Dict]                 ← consolidated unique root causes
similar_cases: List[Dict]              ← retrieved from ChromaDB
applied_rules: List[str]               ← which expert rules fired
severity_assessments: Dict[str, str]   ← location → severity
validated: bool
validation_errors: List[str]
hallucinations_detected: List[str]
missing_data: List[str]
refinement_feedback: Optional[str]     ← feedback injected by validator on retry
final_ddr_html: str
final_ddr_pdf_path: str
iteration_count: int                   ← tracks self-correction iterations (max 3)
agent_logs: List[Dict]                 ← structured logs per agent for debugging
```

---

## LangGraph Workflow Implementation

### Graph Construction Pattern

The workflow is built in `src/graph/workflow.py`. The pattern is: define the StateGraph, add each agent as a named node, connect nodes with edges, add the conditional edge for self-correction, compile, and export the compiled app.

```python
workflow = StateGraph(DDRState)

workflow.add_node("document_understanding", document_understanding_agent)
workflow.add_node("diagnostic_reasoning", diagnostic_reasoning_agent)
workflow.add_node("knowledge_retrieval", knowledge_retrieval_agent)
workflow.add_node("validator", validator_agent)
workflow.add_node("report_synthesis", report_synthesis_agent)

workflow.set_entry_point("document_understanding")
workflow.add_edge("document_understanding", "diagnostic_reasoning")
workflow.add_edge("diagnostic_reasoning", "knowledge_retrieval")
workflow.add_edge("knowledge_retrieval", "validator")

workflow.add_conditional_edges(
    "validator",
    should_refine,           ← routing function
    {
        "refine": "diagnostic_reasoning",
        "continue": "report_synthesis"
    }
)

workflow.add_edge("report_synthesis", END)
app = workflow.compile()
```

### Routing Function

`should_refine(state: DDRState) -> str` returns "refine" if `state["validated"]` is False and `state["iteration_count"]` is less than 3. Returns "continue" otherwise. The iteration cap prevents infinite loops. When the cap is hit and the report is still unvalidated, the report synthesis agent must include a warnings section flagging the specific validation failures.

### How to Invoke

```python
result = app.invoke({
    "inspection_pdf_path": "data/inspection_report.pdf",
    "thermal_pdf_path": "data/thermal_report.pdf",
    "iteration_count": 0,
    "agent_logs": []
})
```

---

## Agent 1 — Document Understanding

**File:** `src/agents/document_understanding.py`

**Responsibility:** Extract all meaningful information from both PDFs and organize it into a structured semantic graph. This agent does not reason — it reads and structures.

**What it does step by step:**

1. Calls `pdf_parser.py` to extract text with structural awareness (headings, sections, tables).
2. Calls `pdf_parser.py` to extract all images with page numbers and position metadata.
3. For each image, calls `image_analyzer.py` to generate a natural language description of what the image shows (dampness patch, thermal hotspot, crack pattern, etc.).
4. Tags each image with the location it belongs to by cross-referencing the surrounding text.
5. Sends the structured text to the LLM with the extraction prompt below.
6. Takes the LLM response and builds a NetworkX semantic graph with `memory.py`.
7. Writes all results to state.

**Extraction Prompt Pattern:**

The prompt follows the React (Reasoning + Acting) pattern — it tells the model its role, gives it a structured task, specifies exact output format, and gives an example of expected JSON shape.

```
System: You are a senior building diagnostics expert analyzing an inspection report.
Your task is to extract structured information with precision.
Never invent information not present in the text.

User:
Extract the following from this inspection report text:

1. ROOMS AND SPACES: List every room, corridor, terrace, and external element mentioned.
2. SPATIAL RELATIONSHIPS: For each pair of spaces, state whether one is above, below, 
   or adjacent to the other. Only include relationships explicitly stated or clearly implied.
3. OBSERVATIONS (negative side): For each symptom, extract:
   - location (exact as written)
   - symptom description
   - extent (if mentioned)
4. FINDINGS (positive side): For each cause or defect, extract:
   - location
   - defect type
   - description
   - extent (if mentioned)

Return ONLY valid JSON matching this schema:
{
  "rooms": ["Hall", "Bathroom", ...],
  "spatial_relationships": [
    {"room_a": "Bathroom", "relation": "above", "room_b": "Hall"}
  ],
  "observations": [
    {"location": "Hall Ceiling", "symptom": "dampness", "extent": "1.2m x 0.8m"}
  ],
  "findings": [
    {"location": "Bathroom Floor", "defect_type": "tile joint gaps", "description": "...", "extent": "..."}
  ]
}

Text:
{extracted_text}
```

**Semantic Graph Construction:**

After the LLM returns JSON, `memory.py` builds the graph. Each room becomes a node. Each spatial relationship becomes a directed edge. Each observation gets attached to its location node as a node attribute. Each finding gets attached similarly. This graph is the foundation for spatial reasoning in Agent 2.

---

## Agent 2 — Diagnostic Reasoning

**File:** `src/agents/diagnostic_reasoning.py`

**Responsibility:** Connect observations (symptoms) to their root causes using spatial traversal of the semantic graph combined with LLM causal inference. This agent thinks — it does not just pass data forward.

**What it does step by step:**

1. Iterates over every observation in state.
2. For each observation, queries the semantic graph using `spatial_reasoner.py` to find what rooms are spatially above, adjacent to, or directly connected to the observation's location.
3. For each spatially related room, checks whether that room has any findings (defects).
4. For each candidate (observation, related finding) pair, sends a causal reasoning prompt to the LLM.
5. If this is a retry (iteration_count > 0), the refinement_feedback from the validator is prepended to every prompt so the model knows what it got wrong last time.
6. Assembles all correlations and writes to state.

**Causal Reasoning Prompt Pattern:**

This also follows React — the model is told to reason step by step before giving its answer, and the output format is enforced.

```
System: You are a structural diagnostics expert.
You must determine whether a building defect is the root cause of a symptom.
Think step by step. Only conclude causation if there is physical plausibility.
Never speculate beyond what the evidence supports.

User:
SYMPTOM: {symptom} observed at {symptom_location}
CANDIDATE ROOT CAUSE: {defect_type} at {cause_location}
SPATIAL RELATIONSHIP: {cause_location} is {relationship} {symptom_location}

Step 1: Is there a plausible physical mechanism for this defect to cause this symptom?
Step 2: Does the spatial relationship support this (e.g., water flows downward)?
Step 3: What is your confidence level (0.0 to 1.0)?

Return ONLY valid JSON:
{
  "is_causal": true,
  "confidence": 0.87,
  "mechanism": "Water seeps through tile joint gaps and accumulates above the ceiling of the hall below",
  "supporting_logic": ["Bathroom is directly above Hall", "Tile gaps allow water ingress", "Dampness pattern consistent with overhead seepage"]
}

{refinement_feedback_if_retry}
```

**Spatial Reasoning Helpers (spatial_reasoner.py):**

- `get_rooms_above(graph, location)` → returns list of rooms whose node has an "above" edge pointing to location
- `get_rooms_adjacent(graph, location)` → returns list of rooms with "adjacent_to" edge
- `get_findings_at(graph, location)` → returns all finding nodes attached to a given location node
- `get_observations_at(graph, location)` → returns all observation nodes at a location

---

## Agent 3 — Knowledge Retrieval

**File:** `src/agents/knowledge_retrieval.py`

**Responsibility:** Enhance and validate the correlations from Agent 2 using two mechanisms — a deterministic rules engine and a vector similarity search over a domain knowledge base.

**Rules Engine (rules_engine.py):**

Rules are stored as Python dicts with condition functions and action functions. Each rule checks specific fields of a correlation and either boosts confidence, adds to reasoning, or flags the correlation.

Example rules:
- IF defect_type contains "tile gap" AND symptom contains "seepage" AND season context is "monsoon" THEN set confidence floor to 0.90 and append "[Rule: Tile gaps during monsoon → confirmed grouting failure]"
- IF defect_type contains "crack" AND crack width > 3mm THEN set severity to "high" and append "[Rule: Structural crack width threshold exceeded]"
- IF symptom is "efflorescence" AND location is "external wall" THEN root cause must include water infiltration consideration
- IF observation location is "ceiling" AND no room_above found in graph THEN mark as "inconclusive — spatial context missing"

Rules fire deterministically. Their outputs are appended to the LLM reasoning, not replacing it. This hybrid approach gives both the precision of expert rules and the flexibility of LLM reasoning.

**Severity Matrix (severity_matrix.py):**

A nested dict lookup: severity = matrix[symptom_type][location_type][extent_category]. Extent categories are defined as percentage ranges (< 10%, 10–30%, > 30%) or size ranges. If an LLM-assigned severity conflicts with the matrix, the matrix wins and a note is logged.

**Vector Store (ChromaDB):**

A collection of past DDR case summaries is embedded and stored in ChromaDB. On each run, the current set of observations is embedded and used to retrieve the three most similar past cases. These cases are added to state["similar_cases"] and referenced in the report synthesis stage as "Similar Cases" evidence.

---

## Agent 4 — Validator (Self-Critic)

**File:** `src/agents/validator.py`

**Responsibility:** This is the most critical agent. It prevents the system from generating hallucinated or inconsistent claims. Every factual claim in the correlations is checked against the extracted source text. If any claim cannot be grounded, validation fails and the system loops back.

**Validation checks performed:**

**Check 1 — Hallucination detection:**
For every correlation, the symptom description must appear (or be clearly paraphrasable) within `state["extracted_text"]`. The validator uses both keyword matching and an LLM grounding check. The grounding prompt asks: "Does this claim appear in the source text? Answer yes or no with a one-sentence justification." If the LLM says no, the claim is flagged as a hallucination.

**Check 2 — Root cause grounding:**
Same as Check 1 but for the root cause side of every correlation. The finding that is claimed to be the root cause must exist in the extracted findings from Agent 1.

**Check 3 — Confidence–severity consistency:**
If a correlation has severity "high" but confidence below 0.70, this is flagged as a validation error. High severity claims need strong confidence.

**Check 4 — Missing data detection:**
The validator checks whether key building elements (external wall, terrace, bathroom waterproofing, overhead tank) have any data at all. If they are missing, they are recorded in `state["missing_data"]`. Missing data is not a validation failure — it is informational and gets surfaced in the report as "data not available / not inspected."

**Check 5 — Spatial plausibility:**
For every correlation, the validator checks the semantic graph to confirm the claimed spatial relationship actually exists as a graph edge. If a correlation claims "Bathroom is above Hall" but the graph has no such edge, this is flagged.

**Refinement Feedback Construction:**

When validation fails, the validator constructs a structured feedback string and writes it to `state["refinement_feedback"]`. This string is injected into Agent 2's prompts on the next iteration. The feedback format is:

```
VALIDATION FEEDBACK FOR RETRY {iteration_count}:
The following claims were not found in the source documents and must be removed or corrected:
- [list of hallucinations with specific location in the claim]

The following spatial relationships are not supported by the building structure data:
- [list of unsupported relationships]

On retry, you must ONLY use information explicitly present in the extracted text.
Do not infer or speculate. If you cannot form a correlation without these claims, 
mark that correlation as inconclusive.
```

---

## Agent 5 — Report Synthesis

**File:** `src/agents/report_synthesis.py`

**Responsibility:** Transform the validated state into a professional client-ready DDR PDF. This agent writes like a consultant — clear, structured, actionable.

**What it does step by step:**

1. Groups observations by area (Hall, Bathroom, External Wall, etc.).
2. For each area, pairs observations with their validated correlations and root causes.
3. Calls a summarization LLM prompt to generate client-friendly language for each finding.
4. Maps images to the correct sections using location tags on ImageEvidence objects.
5. Generates prioritized recommendations based on severity assessments.
6. Includes the missing_data items as a "Scope Limitations" section.
7. If iteration_count reached 3 without full validation, adds a "Validation Warnings" section listing unresolved issues.
8. Renders all data into the Jinja2 HTML template.
9. Converts HTML to PDF using WeasyPrint.

**Report Summarization Prompt Pattern:**

```
System: You are a property consultant writing a Defect Diagnostic Report for a client.
Write in clear, professional English. Use plain language — not technical jargon.
Be specific about locations and causes. Be actionable in recommendations.
Never invent details not provided to you.

User:
Area: {area_name}
Observation: {symptom} observed at {location}
Root Cause: {root_cause} at {cause_location}
Confidence: {confidence}
Evidence: {supporting_evidence_list}

Write a 2-3 sentence diagnostic summary for this finding suitable for a client report.
Then write one specific, actionable recommendation.

Return JSON:
{
  "diagnostic_summary": "...",
  "recommendation": "..."
}
```

**DDR Report Template (ddr_report.html):**

The Jinja2 template produces a structured PDF with these sections in order:
- Cover page with property details and report date
- Executive Summary (overall condition assessment, number of defects by severity)
- Table of Contents
- For each area: heading, observation description, annotated image if available, root cause, diagnostic summary, recommendation
- Similar Cases reference (if retrieved)
- Scope Limitations (missing data)
- Validation Warnings (if any, from unresolved self-correction)
- Appendix: raw extracted data table

---

## Prompt Engineering Patterns Used Throughout

**React Pattern (Reason + Act):**
Every prompt that requires inference tells the model to reason step by step before producing output. The reasoning steps are explicitly listed in the prompt so the model cannot skip them.

**Role Anchoring:**
Every system prompt opens by defining the model's persona and expertise level. "You are a senior building diagnostics expert" sets the prior for domain-appropriate reasoning.

**Output Format Enforcement:**
Every prompt that expects structured data ends with "Return ONLY valid JSON matching this schema" followed by the exact schema with field names, types, and an example. The phrase "ONLY" prevents the model from adding explanation text around the JSON.

**Negative Constraints:**
Every extraction prompt explicitly says "Never invent information not present in the text." This is a direct instruction that reduces hallucination significantly compared to prompts without it.

**Feedback-Aware Retry Prompts:**
When the validator triggers a retry, the feedback is injected at the start of the user message (not the system message) so the model sees it as fresh context. It is labeled "VALIDATION FEEDBACK FOR RETRY {n}" so the model treats it as an authoritative correction.

**Grounding Verification Prompt:**
The validator uses a binary verification prompt ("Does this claim appear in the source text? Yes or no with one-sentence justification") that forces a factual check rather than an opinion.

---

## Semantic Graph Design

The graph is a NetworkX DiGraph. It is built in `src/graph/memory.py` and is part of the DDRState from Agent 1 onward.

**Node types and their attributes:**
- Room node: `type="room"`, `name`, `level` (floor number if known)
- Symptom node: `type="symptom"`, `description`, `severity`, `location`
- Finding node: `type="finding"`, `defect_type`, `description`, `location`

**Edge types:**
- `above` / `below` — spatial vertical relationship between rooms
- `adjacent_to` — spatial horizontal relationship
- `has_symptom` — from room node to symptom node
- `has_finding` — from room node to finding node
- `causes` — from finding node to symptom node (added by Agent 2 after correlation)

**Why NetworkX and not a dict:**
The graph enables traversal queries that are impossible with nested dicts. `get_rooms_above(graph, "Hall")` traverses all incoming `above` edges to the Hall node. This traversal is what enables spatial reasoning — without it, correlating a ceiling symptom to a floor defect above requires the LLM to guess, which it may do incorrectly.

---

## Memory Layer Architecture

**src/graph/memory.py** exposes two things:

**SemanticGraph class:**
Wraps a NetworkX DiGraph with helper methods. `add_room`, `add_spatial_relationship`, `add_symptom_to_room`, `add_finding_to_room`, `add_causal_link`, `get_rooms_above`, `get_rooms_adjacent`, `get_findings_at`, `get_observations_at`, `to_dict` (for serialization into state), `from_dict` (for deserialization).

**VectorStoreWrapper class:**
Wraps a ChromaDB persistent client. Exposes `add_case(case_dict)`, `search_similar(observations_list, k=3)`. Embeddings use the default ChromaDB sentence-transformers model (all-MiniLM-L6-v2). The persistent client stores to `./data/vector_store/` which is gitignored.

---

## Error Handling and Edge Cases

**Missing images:** If `pdf2image` fails on a page, the system logs the failure and continues. ImageEvidence objects for that page are omitted. The report notes which pages had extraction failures.

**LLM structured output failure:** Every LLM call that expects JSON is wrapped in a try-except. If JSON parsing fails, the agent retries the same call once with an additional instruction appended: "Your previous response was not valid JSON. Return ONLY the JSON object, no other text." If it fails again, the agent writes a default empty/error object to state and logs the failure.

**Empty spatial graph:** If Agent 1 finds no spatial relationships (e.g., inspection report has no floor layout information), Agent 2 cannot use graph traversal. In this case, Agent 2 falls back to a direct LLM correlation prompt that asks the model to reason from room names alone (e.g., "bathroom" and "ceiling below bathroom" can be correlated by naming convention).

**ChromaDB cold start:** On the first run, the vector store has no cases. The `search_similar` call returns an empty list gracefully. The report simply omits the "Similar Cases" section.

**iteration_count = 3 with validation still failing:** The report synthesis agent detects `validated = False` and `iteration_count >= 3`. It includes all correlations with a clearly labeled "Unvalidated — use with caution" flag on each affected item. The Validation Warnings section lists every unresolved hallucination. The report is still generated — it is not blocked.

---

## Testing Strategy

Each agent is independently testable because each takes a state dict and returns a state dict. Tests use fixture state objects with known values.

**test_document_understanding.py:** Uses a sample PDF with known content. Asserts that specific rooms, observations, and findings appear in the output state. Asserts that the semantic graph has the correct nodes and edges.

**test_diagnostic_reasoning.py:** Uses a fixture state with a pre-built semantic graph and known observations/findings. Asserts that the correct correlations are produced with confidence above threshold.

**test_validator.py:** Uses fixture states with intentional hallucinations injected. Asserts that `validated` is False and that the specific hallucinated claim appears in `hallucinations_detected`. Also tests the clean case — asserts `validated` is True when all claims are grounded.

**test_workflow_integration.py:** End-to-end test using the real sample PDFs. Asserts that the final state has a non-empty `final_ddr_pdf_path` and that the PDF file exists at that path.

---

## Environment Variables

All secrets and configuration are in `.env`. The `.env.example` shows every required variable.

```
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama3-70b-8192
CHROMA_PERSIST_DIR=./data/vector_store
OUTPUT_DIR=./outputs
LOG_LEVEL=INFO
MAX_CORRECTION_ITERATIONS=3
```

---

## Logging Pattern

Every agent writes a structured log entry to `state["agent_logs"]` at completion:

```python
state["agent_logs"].append({
    "agent": "document_understanding",
    "timestamp": datetime.utcnow().isoformat(),
    "status": "success",
    "rooms_found": len(rooms),
    "observations_found": len(observations),
    "findings_found": len(findings),
    "images_extracted": len(images),
    "graph_nodes": graph.number_of_nodes(),
    "graph_edges": graph.number_of_edges()
})
```

This makes the system fully observable. After a run, `state["agent_logs"]` is a complete execution trace that can be printed, saved, or surfaced in a debug UI.

---

## What Makes This Legendary (The Non-Negotiables)

**Semantic graph over flat JSON:** The graph enables spatial traversal. This is what separates reasoning from extraction. Any system that does not have spatial awareness cannot reliably connect a ceiling symptom to a floor defect above it.

**Self-correction loop with grounded feedback:** Not validation that blocks — validation that teaches. The feedback string tells the model exactly what it got wrong and why. This is a production pattern used in real AI systems, not a demo trick.

**Hybrid knowledge — rules + LLM:** The rules engine catches deterministic patterns (crack > 3mm = structural) that the LLM might hedge on. The LLM handles the ambiguous cases that rules cannot enumerate. Together they outperform either alone.

**Every LLM output is a Pydantic model:** No raw dict parsing. If the LLM returns malformed output, it is caught at the model validation step before it corrupts the state. This makes debugging fast and precise.

**Structured agent logs:** After a run, you know exactly what every agent did, how many items it found, and how long it took. This is production observability, not a black box.

**Images as first-class evidence:** Images are not appended decoratively. They are extracted, described, tagged to locations, linked to observations, and placed inline in the relevant report sections. They are evidence, not decoration.