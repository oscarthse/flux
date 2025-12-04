# Flux Evaluation Rules (Strict)

1.  **Spec Reference**: Every agent MUST reference `/agents/resources/flux_spec_v1.md`.
2.  **Math Audit**: Math-heavy tasks MUST be reviewed by **[MATH_AUDIT]**.
3.  **Security Audit**: Anything related to RLS MUST be reviewed by **[SEC]**.
4.  **Backend Review**: Any UI implementation MUST be reviewed by **[BACKEND]**.
5.  **QA Gate**: ANYTHING merged MUST pass tests from **[QA]**.
6.  **Orchestrator Gate**: The **[ORCH]** MUST return work when:
    *   math is unclear
    *   assumptions are undocumented
    *   code is too magical
    *   no test plan exists
7.  **Professionalism**: All agents must respond in structured, professional engineering style.
