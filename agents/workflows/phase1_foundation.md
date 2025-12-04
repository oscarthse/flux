# Phase 1 — Foundation & Ingestion Multi-Agent Workflow

## Flow Definition

1.  **Architecture + DB**
    *   **[ARCH]** designs API/Worker separation, ingestion pipeline, event flow.
    *   **[DATA]** designs DB schema + RLS + recipe DAG.
    *   **[SEC]** reviews RLS isolation.
    *   **[QA]** reviews DB constraints.

2.  **Ingestion Engine**
    *   **[BACKEND]** implements FastAPI webhooks -> Redis -> Worker ingestion tasks.
    *   **[DATA]** supports with DB writes.
    *   **[MATH_AUDIT]** reviews recipe explosion + modifier math.
    *   **[QA]** reviews ingestion tests on synthetic POS data.

3.  **Triage Room UI**
    *   **[UI]** implements HTMX interface for ghost items and recipe mapping.
    *   **[BACKEND]** reviews HTMX contract correctness.
    *   **[QA]** reviews E2E ingest → triage → re-run explosion.

4.  **Documentation**
    *   **[DOCS]** updates Onboarding, architecture, RLS design, ingestion flow.

## Completion Rule
**[ORCH]** marks complete when:
*   QA tests pass.
*   SEC approved.
*   MATH_AUDIT approved.
