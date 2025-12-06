-- Fix Row-Level Security Policies for Flux Platform
-- This script creates the tenant isolation helper function and re-enables all RLS policies

-- Drop and recreate the helper function with proper dollar-quoting to avoid parse errors
DROP FUNCTION IF EXISTS current_tenant_id();

CREATE FUNCTION current_tenant_id() RETURNS UUID AS
$func$
BEGIN
    -- Returns the tenant_id set in the session variable
    -- Usage: SET LOCAL app.current_tenant = 'uuid';
    RETURN current_setting('app.current_tenant', true)::UUID;
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

-- Now recreate all RLS policies
-- Policy names are consistent: tenant_isolation

-- Users table
DROP POLICY IF EXISTS tenant_isolation ON users;
CREATE POLICY tenant_isolation ON users USING (tenant_id = current_tenant_id());

-- Menu Items
DROP POLICY IF EXISTS tenant_isolation ON menu_items;
CREATE POLICY tenant_isolation ON menu_items USING (tenant_id = current_tenant_id());

-- Ingredients
DROP POLICY IF EXISTS tenant_isolation ON ingredients;
CREATE POLICY tenant_isolation ON ingredients USING (tenant_id = current_tenant_id());

-- Recipes
DROP POLICY IF EXISTS tenant_isolation ON recipes;
CREATE POLICY tenant_isolation ON recipes USING (tenant_id = current_tenant_id());

-- Inventory Batches
DROP POLICY IF EXISTS tenant_isolation ON inventory_batches;
CREATE POLICY tenant_isolation ON inventory_batches USING (tenant_id = current_tenant_id());

-- Sales Orders
DROP POLICY IF EXISTS tenant_isolation ON sales_orders;
CREATE POLICY tenant_isolation ON sales_orders USING (tenant_id = current_tenant_id());

-- Order Line Items
DROP POLICY IF EXISTS tenant_isolation ON order_line_items;
CREATE POLICY tenant_isolation ON order_line_items USING (tenant_id = current_tenant_id());

-- Triage Items
DROP POLICY IF EXISTS tenant_isolation ON triage_items;
CREATE POLICY tenant_isolation ON triage_items USING (tenant_id = current_tenant_id());

-- Forecasts
DROP POLICY IF EXISTS tenant_isolation ON forecasts;
CREATE POLICY tenant_isolation ON forecasts USING (tenant_id = current_tenant_id());

-- Purchase Orders
DROP POLICY IF EXISTS tenant_isolation ON purchase_orders;
CREATE POLICY tenant_isolation ON purchase_orders USING (tenant_id = current_tenant_id());

-- PO Line Items
DROP POLICY IF EXISTS tenant_isolation ON po_line_items;
CREATE POLICY tenant_isolation ON po_line_items USING (tenant_id = current_tenant_id());

-- Inventory Log
DROP POLICY IF EXISTS tenant_isolation ON inventory_log;
CREATE POLICY tenant_isolation ON inventory_log USING (tenant_id = current_tenant_id());

-- Staff Schedule
DROP POLICY IF EXISTS tenant_isolation ON staff_schedule;
CREATE POLICY tenant_isolation ON staff_schedule USING (tenant_id = current_tenant_id());

-- Lost Sales
DROP POLICY IF EXISTS tenant_isolation ON lost_sales;
CREATE POLICY tenant_isolation ON lost_sales USING (tenant_id = current_tenant_id());
