# Product Use Case: Industrial Controls Release Assurance

## 1. Core Product Definition
This product is a read-only, human-reviewed release audit tool for Rockwell PLC projects[cite: 1]. It is deployed before Factory Acceptance Testing (FAT) or deployment to automatically determine what process behavior may be affected by code changes and what focused regression tests are required[cite: 1, 2].

## 2. Target Audience & Business Value
*   **Customer:** North American controls integrators (20 to 200 employees) delivering fixed-price water/wastewater projects[cite: 1, 2].
*   **Daily User:** Lead controls engineer, QA reviewer, or FAT lead[cite: 1].
*   **Pain Point:** Missed behavioral impacts during manual code reviews cause failed FATs, field rework, project delays, and lost margin[cite: 1, 2].

## 3. Hard Safety Boundaries (AI Constraints)
*   **Read-Only:** The system NEVER connects to or writes to a live controller, HMI, or production system[cite: 1].
*   **No Autonomous Approval:** The system does not claim a release is safe or approved; a qualified engineer must explicitly approve or reject all findings[cite: 1].
*   **No Hallucinated Logic:** The AI must not invent missing requirements or code behavior[cite: 1]. High-confidence findings must show exact source evidence and specific PLC locations[cite: 1].

## 4. Required Inputs
1.  **Baseline PLC Project (L5X):** Current approved controller XML export[cite: 1].
2.  **Revised PLC Project (L5X):** Proposed controller XML export with changes[cite: 1].
3.  **SOO/FDS (PDF/DOCX):** Text documents containing operating requirements[cite: 1].
4.  *(Optional)* I/O lists and Alarm lists in XLSX/CSV formats[cite: 1].

## 5. Required Outputs
1.  **Change Register:** Structured list of what changed and where[cite: 1].
2.  **Impact Register:** Affected equipment, sequences, and behaviors[cite: 1].
3.  **Regression-Test Plan:** Proposed test purpose, steps, and expected results[cite: 1].
4.  **Export Package:** A final, human-reviewed PDF and CSV traceability report[cite: 1].