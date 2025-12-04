"""
Worker Integration Tests - Inventory Optimization Engine

Tests the inventory optimization worker engine in isolation
and integration with the database.
"""
import pytest
from datetime import date, timedelta
from services.worker.engines.inventory import generate_draft_orders


@pytest.mark.worker
@pytest.mark.integration
def test_optimization_creates_pos_with_forecasts(tenant_id, db_connection):
    """Test: Optimization creates POs when forecasts indicate need."""
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

        # Setup: Create ingredient
        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days, unit)
            VALUES (%s, 'Test Ingredient', 5.00, 2, 'kg')
            RETURNING id
        """, (tenant_id,))
        ing_id = cur.fetchone()[0]

        # Create menu item and recipe
        cur.execute("""
            INSERT INTO menu_items (tenant_id, name, price)
            VALUES (%s, 'Test Item', 10.00)
            RETURNING id
        """, (tenant_id,))
        menu_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
            VALUES (%s, %s, %s, 1.0)
        """, (tenant_id, menu_id, ing_id))

        # Create forecasts for next 7 days (high demand)
        for i in range(7):
            forecast_date = date.today() + timedelta(days=i)
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 50.0)
            """, (tenant_id, menu_id, forecast_date))

        db_connection.commit()

    # Run optimization
    generate_draft_orders(tenant_id, db_connection)

    # Verify: PO was created
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'draft'")
        count = cur.fetchone()[0]
        assert count > 0, "Optimization should create draft PO with high forecast demand"


@pytest.mark.worker
@pytest.mark.integration
def test_optimization_with_no_forecasts(tenant_id, db_connection):
    """Test: No forecasts = no purchase orders created."""
    # Run optimization without any forecasts
    generate_draft_orders(tenant_id, db_connection)

    # Verify: No POs created
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT COUNT(*) FROM purchase_orders")
        count = cur.fetchone()[0]
        assert count == 0, "No forecasts should result in no POs"


@pytest.mark.worker
@pytest.mark.integration
def test_optimization_respects_tenant_isolation(tenant_id, other_tenant_id, db_connection):
    """Test: Optimization for Tenant A doesn't create POs for Tenant B."""
    # Setup: Create ingredient for Tenant A
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days)
            VALUES (%s, 'Tenant A Ingredient', 5.00, 2)
            RETURNING id
        """, (tenant_id,))
        ing_a_id = cur.fetchone()[0]

        # Create ingredient for Tenant B
        cur.execute("SET app.current_tenant_id = %s", (other_tenant_id,))
        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days)
            VALUES (%s, 'Tenant B Ingredient', 5.00, 2)
            RETURNING id
        """, (other_tenant_id,))
        ing_b_id = cur.fetchone()[0]

        db_connection.commit()

    # Run optimization for Tenant A only
    generate_draft_orders(tenant_id, db_connection)

    # Verify: Tenant B has no POs (RLS enforcement)
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (other_tenant_id,))
        cur.execute("SELECT COUNT(*) FROM purchase_orders")
        count = cur.fetchone()[0]
        assert count == 0, "Optimization for Tenant A should not affect Tenant B"


@pytest.mark.worker
@pytest.mark.integration
def test_po_line_items_calculated_correctly(tenant_id, db_connection):
    """Test: PO line items have correct quantities and prices."""
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

        # Create ingredient with known cost
        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days, unit)
            VALUES (%s, 'Known Cost Ingredient', 8.50, 2, 'kg')
            RETURNING id
        """, (tenant_id,))
        ing_id = cur.fetchone()[0]

        # Create menu item and recipe
        cur.execute("""
            INSERT INTO menu_items (tenant_id, name, price)
            VALUES (%s, 'Test Dish', 15.00)
            RETURNING id
        """, (tenant_id,))
        menu_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
            VALUES (%s, %s, %s, 0.5)
        """, (tenant_id, menu_id, ing_id))

        # Create forecasts
        for i in range(7):
            forecast_date = date.today() + timedelta(days=i)
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 40.0)
            """, (tenant_id, menu_id, forecast_date))

        db_connection.commit()

    # Run optimization
    generate_draft_orders(tenant_id, db_connection)

    # Verify: Line item has correct unit price
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("""
            SELECT unit_price FROM po_line_items
            WHERE ingredient_id = %s
            LIMIT 1
        """, (ing_id,))
        result = cur.fetchone()
        assert result is not None, "PO line item should exist"
        assert float(result[0]) == 8.50, "Unit price should match ingredient cost"
