# Execution Plan: YC Demo Rapid Milestone Delivery

**Goal:** Process a baseline L5X, revised L5X, and SOO/FDS to produce a reviewable, technically accurate change-impact list and regression test plan. The end-to-end demo must run in under 90 seconds and demonstrate 100% factual accuracy on logic states.

## Milestone 1: Deterministic L5X Fact Extraction
*   **Task:** Build a strict XML parser to ingest L5X files and extract exact changes without LLM interpretation. For every changed rung, output a structured JSON containing: `routine`, `rung_number`, `baseline_logic`, `revised_logic`, `instructions_added`, `instructions_removed`, `output_tags`, and `input_tags`.
*   **Validation Check:** The script accurately outputs the deterministic JSON object for the AFI addition (detecting `instructions_added: ["AFI"]` and `output_tags: ["CHWP02_FailoverRequest"]`) without any AI calls.

## Milestone 2: Industrial Rule Engine Implementation
*   **Task:** Implement a hardcoded, lightweight industrial rule layer for six high-value instructions: AFI, XIC, XIO, OTE, TON, and MOV. 
*   **Validation Check:** If the parser detects an AFI, the backend automatically attaches the rule: *"AFI always evaluates false. If an AFI is added before an output instruction, the downstream output path is disabled."*

## Milestone 3: Rich SOO Document Mapping (Vector DB)
*   **Task:** Extract text blocks from the SOO PDF, retaining rich metadata (Document Name, Revision, Page Number, Section Number). Map the structured PLC change to the SOO requirements.
*   **Validation Check:** The vector database returns the correct failover requirement for `CHWP02` along with its exact page and section numbers.

## Milestone 4: Strict AI Reasoning & Test Generation
*   **Task:** Pass the deterministic facts, the industrial rules, and the mapped SOO requirement to the strongest reasoning model (e.g., GPT-4o). Use a highly constrained system prompt to prevent hallucination of programmer intent. Output findings into three strict categories: `Approved change`, `Suspected regression`, `Needs review`.
*   **Validation Check:** The model correctly explains that the AFI prevents the failover request from becoming true, specifies that intent is unknown, and drafts a test to be run in a simulation/FAT environment.

## Milestone 5: UI Refinement & 7-Point Evidence Stack
*   **Task:** Update the frontend Next.js interface. Remove technical jargon from the upload page. Add a compact summary ribbon (Changes, Requirements, Total Findings, Criticals, Tests). Consolidate the middle pane into a single 7-point evidence stack (Routine/rung, baseline, revised, SOO text/page, proposed test, expected result).
*   **Validation Check:** A customer can understand exactly what changed and why it matters without clicking through multiple tabs or panels.