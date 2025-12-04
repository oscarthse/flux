# Forecasting Engine Design (Engine B)

## Goal
Predict future sales (item quantities) to drive inventory ordering.

## Constraints
*   **No Synthetic Data**: Models must learn strictly from `sales_orders` (ingested data).
*   **Model**: Start with Moving Average (MA) for robustness.

## Schema Additions
```sql
CREATE TABLE forecasts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    menu_item_id UUID REFERENCES menu_items(id),
    forecast_date DATE NOT NULL,
    predicted_quantity DECIMAL(10,2),
    confidence_interval_lower DECIMAL(10,2),
    confidence_interval_upper DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    model_version VARCHAR(50),
    UNIQUE(tenant_id, menu_item_id, forecast_date)
);
ALTER TABLE forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecasts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON forecasts USING (tenant_id = current_tenant_id());
```

## Implementation Plan
1.  **[DATA]**: Apply schema update.
2.  **[ML]**: Implement `services/worker/engines/forecasting.py`.
    *   `generate_forecast(tenant_id, item_id)`: Fetches last N days of sales from `order_line_items`, calculates avg, saves to `forecasts`.
3.  **[BACKEND]**: Create nightly cron task.
