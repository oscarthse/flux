import pytest
from datetime import date, timedelta
from services.worker.engines.inventory import calculate_inventory_health, generate_draft_orders
from lib.flux_lib.db import get_db_connection

def test_dormant_inventory_logic(db_setup):
    """
    Verify that an ingredient with 0 usage forecast:
    1. Has 'dormant' status.
    2. Has 0 burn rate.
    3. Does NOT generate a purchase order.
    """
    tenant_id = "test-tenant-logic"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Setup Data
            # Create Ingredient "Dormant Spice"
            cur.execute("""
                INSERT INTO ingredients (id, tenant_id, name, category, unit, cost_per_unit, lead_time_days)
                VALUES (%s, %s, 'Dormant Spice', 'Spices', 'kg', 10.0, 2)
            """, ('dormant-1', tenant_id))

            # Create Stock (10kg)
            cur.execute("""
                INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity, received_date, expiry_date)
                VALUES (%s, %s, 'dormant-1', 10.0, 10.0, CURRENT_DATE, CURRENT_DATE + INTERVAL '1 year')
            """, ('batch-1', tenant_id))

            # Create Menu Item & Recipe (but NO Forecasts)
            cur.execute("INSERT INTO menu_items (id, tenant_id, name, price) VALUES (%s, %s, 'Spicy Dish', 15.0)", ('menu-1', tenant_id))
            cur.execute("INSERT INTO recipes (id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, 'dormant-1', 0.1)", ('recipe-1', 'menu-1'))

            conn.commit()

            # 2. Run Health Calculation
            health_report = calculate_inventory_health(tenant_id, conn)

            # 3. Verify Health
            spice_health = next(h for h in health_report if h.ingredient_id == 'dormant-1')

            assert spice_health.burn_rate == 0.0, "Burn rate should be 0 without forecasts"
            assert spice_health.status == 'dormant', f"Status should be 'dormant', got {spice_health.status}"
            assert spice_health.should_order is False, "Should not order dormant items"
            assert spice_health.revenue_risk == 0.0, "Revenue risk should be 0"
            assert spice_health.usage_explanation == "No forecasted usage"

            # 4. Run Order Generation
            generate_draft_orders(tenant_id, conn)

            # 5. Verify No PO Created
            cur.execute("SELECT COUNT(*) FROM purchase_orders WHERE tenant_id = %s", (tenant_id,))
            count = cur.fetchone()[0]
            assert count == 0, "No PO should be created for dormant items"

def test_critical_inventory_logic(db_setup):
    """
    Verify that an ingredient with High usage:
    1. Has 'critical' status.
    2. Has correct burn rate.
    3. Generates a purchase order with correct reasoning.
    """
    tenant_id = "test-tenant-logic-2"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Setup Data
            # Create Ingredient "Critical Rice" (Low Stock)
            cur.execute("""
                INSERT INTO ingredients (id, tenant_id, name, category, unit, cost_per_unit, lead_time_days)
                VALUES (%s, %s, 'Critical Rice', 'Grains', 'kg', 2.0, 1)
            """, ('crit-1', tenant_id))

            # Stock: 1kg
            cur.execute("""
                INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity, received_date)
                VALUES ('batch-2', %s, 'crit-1', 1.0, 1.0, CURRENT_DATE)
            """, (tenant_id,))

            # Menu Item: Paella ($20)
            cur.execute("INSERT INTO menu_items (id, tenant_id, name, price) VALUES ('menu-2', %s, 'Paella', 20.0)", (tenant_id,))
            cur.execute("INSERT INTO recipes (id, menu_item_id, ingredient_id, quantity) VALUES ('rec-2', 'menu-2', 'crit-1', 0.5)", (tenant_id,))

            # Forecast: 10 Paellas/day for next 7 days (Usage = 5kg/day)
            for i in range(7):
                f_date = date.today() + timedelta(days=i)
                cur.execute("INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity) VALUES (%s, 'menu-2', %s, 10.0)", (tenant_id, f_date))

            conn.commit()

            # 2. Run Health Calculation
            health_report = calculate_inventory_health(tenant_id, conn)
            rice_health = next(h for h in health_report if h.ingredient_id == 'crit-1')

            # 3. Verify Logic
            assert rice_health.burn_rate == 5.0, f"Burn rate should be 5.0, got {rice_health.burn_rate}"
            assert rice_health.current_stock == 1.0
            # Runout: 1kg / 5kg/day = 0.2 days. Runout Date = Today.
            assert rice_health.days_until_runout < 1.0
            assert rice_health.status == 'critical'
            assert rice_health.should_order is True
            assert "Paella" in rice_health.usage_explanation

            # Revenue Risk:
            # Runout today. Lost sales for next 7 days = 10 * 7 = 70 Paellas.
            # Risk = 70 * $20 = $1400.
            # (Note: Logic calculates risk for 7 days AFTER runout. Since runout is today, it captures full week).
            assert rice_health.revenue_risk > 1000.0, f"Revenue risk should be high, got {rice_health.revenue_risk}"

            # 4. Run Order Generation
            generate_draft_orders(tenant_id, conn)

            # 5. Verify PO
            cur.execute("SELECT id FROM purchase_orders WHERE tenant_id = %s", (tenant_id,))
            po_id = cur.fetchone()[0]

            cur.execute("SELECT quantity, reason FROM po_line_items WHERE po_id = %s", (po_id,))
            row = cur.fetchone()
            qty = float(row[0])
            reason = row[1]

            # Order Qty: Lead(1) + Review(3) + Buffer(1) = 5 days coverage.
            # Need: 5 days * 5kg/day = 25kg.
            # Have: 1kg.
            # Order: 24kg.
            assert 23.0 < qty < 25.0, f"Order qty should be ~24kg, got {qty}"
            assert "Runs out in" in reason
