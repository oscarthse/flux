-- schema.sql
-- Flux v1.0 Multi-Tenant Schema with RLS

-- 0. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tenants & Auth
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Helper function for RLS
-- Usage: SET LOCAL app.current_tenant_id = 'uuid';
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id')::UUID;
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 2. Master Data (RLS Enabled)
CREATE TABLE menu_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    external_id VARCHAR(100), -- ID from POS (Square/Toast)
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(tenant_id, external_id)
);
ALTER TABLE menu_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON menu_items USING (tenant_id = current_tenant_id());

CREATE TABLE ingredients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    cost_per_unit DECIMAL(10,2),
    unit VARCHAR(20),
    par_level DECIMAL(10,2),
    reorder_threshold DECIMAL(10,2),
    lead_time_days INT,
    shelf_life_days INT,
    UNIQUE(tenant_id, name)
);
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ingredients USING (tenant_id = current_tenant_id());

-- Recipe DAG (Adjacency List)
CREATE TABLE recipes (
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    menu_item_id UUID REFERENCES menu_items(id),
    ingredient_id UUID REFERENCES ingredients(id),
    quantity DECIMAL(10,4),
    PRIMARY KEY (tenant_id, menu_item_id, ingredient_id)
);
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON recipes USING (tenant_id = current_tenant_id());

-- 3. Inventory Ledger (FEFO Support)
CREATE TABLE inventory_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    ingredient_id UUID REFERENCES ingredients(id),
    quantity DECIMAL(10,2) NOT NULL,
    remaining_quantity DECIMAL(10,2) NOT NULL,
    cost_per_unit DECIMAL(10,2),
    received_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    CHECK (remaining_quantity >= 0)
);
CREATE INDEX idx_inventory_fefo ON inventory_batches (tenant_id, ingredient_id, expires_at ASC) WHERE remaining_quantity > 0;
ALTER TABLE inventory_batches ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inventory_batches USING (tenant_id = current_tenant_id());

-- 4. Transactional Data
CREATE TABLE sales_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    external_id VARCHAR(100), -- POS Order ID
    timestamp TIMESTAMP NOT NULL,
    party_size INT,
    total_amount DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'completed',
    UNIQUE(tenant_id, external_id)
);
ALTER TABLE sales_orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON sales_orders USING (tenant_id = current_tenant_id());

CREATE TABLE order_line_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    order_id UUID REFERENCES sales_orders(id),
    menu_item_id UUID REFERENCES menu_items(id),
    quantity INT,
    price_at_order DECIMAL(10,2)
);
ALTER TABLE order_line_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON order_line_items USING (tenant_id = current_tenant_id());

-- 5. Ingestion Triage (Ghost Items)
CREATE TABLE triage_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    external_id VARCHAR(100) NOT NULL,
    external_name VARCHAR(255),
    source VARCHAR(50), -- 'square', 'toast'
    detected_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'mapped', 'ignored'
    UNIQUE(tenant_id, external_id)
);
ALTER TABLE triage_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE triage_items FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON triage_items USING (tenant_id = current_tenant_id());

-- 6. Operational Logs
CREATE TABLE lost_sales (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    timestamp TIMESTAMP,
    party_size INT,
    reason VARCHAR(50),
    potential_revenue DECIMAL(10,2)
);
ALTER TABLE lost_sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE lost_sales FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON lost_sales USING (tenant_id = current_tenant_id());

CREATE TABLE staff_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE,
    role VARCHAR(50),
    count INT,
    cost DECIMAL(10,2)
);
ALTER TABLE staff_schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_schedule FORCE ROW LEVEL SECURITY;
ALTER TABLE staff_schedule FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON staff_schedule USING (tenant_id = current_tenant_id());

-- 7. Forecasting (Engine B)
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
ALTER TABLE forecasts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON forecasts USING (tenant_id = current_tenant_id());

-- 8. Inventory Optimization (Engine C)
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

-- 9. Inventory Log (Simulator Data)
CREATE TABLE inventory_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL,
    ingredient_id UUID REFERENCES ingredients(id),
    opening_stock DECIMAL(10,2),
    used_qty DECIMAL(10,2),
    restock_qty DECIMAL(10,2),
    waste_qty DECIMAL(10,2),
    closing_stock DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);
ALTER TABLE inventory_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inventory_log USING (tenant_id = current_tenant_id());

-- 10. Staff Schedule (Simulator Data)
CREATE TABLE staff_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL,
    role VARCHAR(100),
    count INTEGER,
    cost DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);
ALTER TABLE staff_schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_schedule FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON staff_schedule USING (tenant_id = current_tenant_id());

-- 11. Lost Sales (Simulator Data)
CREATE TABLE lost_sales (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    timestamp TIMESTAMP NOT NULL,
    party_size INTEGER,
    reason VARCHAR(255),
    potential_revenue DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);
ALTER TABLE lost_sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE lost_sales FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON lost_sales USING (tenant_id = current_tenant_id());
