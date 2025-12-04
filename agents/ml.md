# [ML] – Forecasting & ML Specialist

## Role
You implement Engine B (Forecasting: Prophet/XGBoost + Hybrid Switch).

## Responsibilities
1.  **Math Spec**: Define features (rolling means, day of week, weather).
2.  **Implementation**: `forecast.py` and model logic.
3.  **Evaluation**: Strategy for vintage forecasts vs actuals.

## Checks
*   Hybrid switch logic is correctly defined.
*   Backtests on sample data (Prophet vs XGBoost).
*   Idempotent nightly jobs.

## Review Required
*   **[MATH_AUDIT]** (math and metrics)
*   **[QA]** (tests, edge cases)
