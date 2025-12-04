# Phase 4 — Staffing & Polish Multi-Agent Workflow

## Flow Definition

1.  **Scheduling Model Design**
    *   **[STAFF_OPT]** builds CP-SAT constraint model.
    *   **[MATH_AUDIT]** checks constraints and ensures no degenerate solutions.

2.  **Implementation**
    *   **[STAFF_OPT]** implements `scheduling.py`.
    *   **[BACKEND]** implements worker task "Generate Schedule" and review endpoints.
    *   **[UI]** implements Visual Roster.
    *   **[DEVOPS]** implements notification infra (email/SMS).

3.  **Validation**
    *   **[QA]** runs integration tests on full closed loop (forecast → staffing → inventory).
    *   **[MATH_AUDIT]** validates schedule fairness and constraint satisfaction.

4.  **Documentation**
    *   **[DOCS]** creates admin guides and support playbook.

## Completion Rule
**[ORCH]** marks complete when:
*   Full closed loop tests pass.
*   Schedules are feasible and fair.
*   Docs are complete.
