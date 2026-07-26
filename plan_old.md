# Execution Plan: Rapid Milestone Delivery

**Goal:** Process a baseline L5X, revised L5X, and SOO/FDS to produce a reviewable change-impact list and regression test plan in under 10 minutes[cite: 1].

## Milestone 1: L5X & Document Ingestion
*   **Task:** Build the `lxml` parser to ingest L5X files, validate XML structure, and extract tags/routines[cite: 1]. Build PDF/DOCX text extraction for the SOO/FDS[cite: 1]. Freeze the supported data models and the four change classes (Interlocks, Alarms/Timers, Modes, Sequences)[cite: 1].
*   **Validation Check:** A standalone Python script successfully prints a parsed dictionary of tags from the L5X and extracted text blocks from the SOO PDF.

## Milestone 2: Deterministic Diff & Normalization
*   **Task:** Build the core L5X diff engine to compare baseline and revised structures[cite: 1]. Filter out formatting/metadata noise to isolate true behavioral code changes[cite: 1]. Normalize equipment and tag names into a canonical format[cite: 1].
*   **Validation Check:** The script accurately outputs a list of true behavioral differences between the two sample L5X files while ignoring metadata updates.

## Milestone 3: Mapping & Rules Engine (Qdrant)
*   **Task:** Spin up local Qdrant (Sparse-Dense Hybrid Search). Extract structured requirements from the SOO/FDS language using the local LLM[cite: 1]. Map the L5X code changes to the extracted requirements using exact matches, aliases, and semantic matching[cite: 1].
*   **Validation Check:** Passing a dummy requirement string into a test function returns the correct matching tag from the local Qdrant collection.

## Milestone 4: Configurable AI Test Generation & API
*   **Task:** Use `Instructor` and `LiteLLM` to draft focused regression test steps (prerequisites, expected results) based on the mapped impacts[cite: 1]. Build the FastAPI endpoints to serve the findings and test plans.
*   **Validation Check:** Passing a mock diff and requirement into the function successfully prints a strictly formatted JSON regression test to the terminal.

## Milestone 5: Frontend UI & Human Review Workflow
*   **Task:** Build the Next.js split-view interface showing the change, requirement, evidence, and proposed test[cite: 1]. Implement the human review actions: Accept, Reject, Edit, or Mark Unresolved[cite: 1]. Build the PDF and CSV export package generator[cite: 1].
*   **Validation Check:** The full pipeline runs end-to-end via the web browser, allowing the user to click through the workflow and download the export package.

## Milestone 6: Benchmark Validation
*   **Task:** Run the full pipeline against the provided benchmark datasets (`ground_truth.json`).
*   **Validation Check:** Measure targets to confirm success: < 10-minute processing time, >= 80% high-confidence precision, and 100% deterministic reproducibility on L5X diffs[cite: 1].