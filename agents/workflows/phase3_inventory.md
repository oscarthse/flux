# Phase 3 — Inventory Optimization Multi-Agent Workflow

## Flow Definition

1.  **Inventory Logic Design**
    *   **[INV_OPT]** derives R, S formulas, safety stock, and FEFO logic.
    *   **[MATH_AUDIT]** cross-checks formulas and simulates scenarios (stock-outs, spikes).

2.  **Implementation**
    *   **[INV_OPT]** implements `inventory.py`.
    *   **[BACKEND]** implements worker job "Generate Draft POs" and API endpoints.
    *   **[UI]** implements Smart Order dashboard with override controls.

3.  **Validation**
    *   **[QA]** runs scenario tests (override detection, PO quantities, FEFO).
    *   **[MATH_AUDIT]** verifies simulation results match theory.

4.  **Documentation**
    *   **[DOCS]** documents R/S policy and override feedback loop.

## Completion Rule
**[ORCH]** marks complete when:
*   Simulations pass.
*   Draft POs are accurate.
*   MATH_AUDIT approved.
