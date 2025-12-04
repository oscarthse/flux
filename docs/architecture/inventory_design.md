# Inventory Engine Design (Engine C)

## Goal
Optimize inventory levels to minimize waste and stockouts using an (R, s) policy.

## Logic: (R, s) Policy
*   **s (Reorder Point)**: When stock drops below this, order.
    *   `s = (Daily Forecast * Lead Time) + Safety Stock`
*   **R (Order Up-To Level)**: Target inventory level.
    *   `R = s + (Daily Forecast * Review Period)`
*   **Order Quantity (Q)**: `Q = R - Current Stock`

## Schema Additions
```sql
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    status VARCHAR(20) DEFAULT 'draft', -- draft, ordered, received
    created_at TIMESTAMP DEFAULT NOW(),
    delivery_date DATE
);
ALTER TABLE purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_orders FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON purchase_orders USING (tenant_id = current_tenant_id());

CREATE TABLE po_line_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    po_id UUID REFERENCES purchase_orders(id),
    ingredient_id UUID REFERENCES ingredients(id),
    quantity DECIMAL(10,2),
    unit_price DECIMAL(10,2)
);
ALTER TABLE po_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE po_line_items FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON po_line_items USING (tenant_id = current_tenant_id());
```

## Implementation Plan
1.  **[DATA]**: Apply schema update.
2.  **[INV_OPT]**: Implement `services/worker/engines/inventory.py`.
    *   `generate_draft_orders(tenant_id)`:
        1.  Iterate all ingredients.
        2.  Calculate `s` and `R` using forecasts (mapped from menu items via recipes).
        3.  If `Current Stock < s`, create PO Line Item for `Q = R - Current Stock`.
3.  **[UI]**: Smart Order Dashboard (`smart_order.html`).
