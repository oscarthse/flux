# Phase 2 — Forecasting Loop Multi-Agent Workflow

## Flow Definition

1.  **Forecasting Design**
    *   **[ML]** defines forecasting problem, features, and hybrid switch logic.
    *   **[MATH_AUDIT]** validates hybrid threshold rule and evaluation metrics.

2.  **Implementation**
    *   **[ML]** implements `forecast.py` and model logic.
    *   **[BACKEND]** implements worker tasks for nightly jobs and API for graph data.
    *   **[UI]** implements Actuals vs Forecast graph and Reliability Badge.

3.  **Validation**
    *   **[QA]** runs backtesting harness and verifies vintage forecasts.
    *   **[MATH_AUDIT]** reviews backtest results (MAPE, bias).

4.  **Documentation**
    *   **[DOCS]** updates docs with forecasting model details and reliability metrics.

## Completion Rule
**[ORCH]** marks complete when:
*   Backtests pass criteria.
*   MATH_AUDIT approved.
*   UI displays correct data.
