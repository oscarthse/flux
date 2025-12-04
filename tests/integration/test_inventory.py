import pytest
from datetime import date, timedelta
from decimal import Decimal
from lib.flux_lib.db import get_db_connection
from services.worker.engines.inventory import generate_draft_orders

def test_generate_draft_orders(tenant_id):
    """
    Test that draft orders are generated correctly based on forecasts.
    """

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # 1. Create Ingredient (Lead Time = 2 days)
            cur.execute("""
                INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days)
                VALUES (%s, 'Test Flour', 10.00, 2)
                RETURNING id
            """, (tenant_id,))
            ing_id = cur.fetchone()[0]

            # 2. Create Menu Item & Recipe (1 item uses 0.5 units of Flour)
            cur.execute("""
                INSERT INTO menu_items (tenant_id, name, price)
                VALUES (%s, 'Pizza', 15.00)
                RETURNING id
            """, (tenant_id,))
            menu_item_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
                VALUES (%s, %s, %s, 0.5)
            """, (tenant_id, menu_item_id, ing_id))

            # 3. Insert Forecasts for next 7 days
            # Predict 20 Pizzas/day => 10 units of Flour/day
            for i in range(7):
                f_date = date.today() + timedelta(days=i)
                cur.execute("""
                    INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                    VALUES (%s, %s, %s, 20.0)
                """, (tenant_id, menu_item_id, f_date))

            # 4. Set Current Stock to 0
            # Daily Usage = 10 units
            # Safety Stock = 10 * 2 * 0.5 = 10 units
            # s (Reorder Point) = (10 * 2) + 10 = 30 units
            # R (Order Up-To) = 30 + (10 * 3) = 60 units
            # Current Stock = 0
            # Expected Order = 60 - 0 = 60 units

            conn.commit()

            # Run Engine
            generate_draft_orders(tenant_id, conn)

            # Verify PO
            cur.execute("""
                SELECT id, status FROM purchase_orders
                WHERE tenant_id = %s AND status = 'draft'
            """, (tenant_id,))
            po = cur.fetchone()
            assert po is not None
            po_id = po[0]

            # Verify Line Item
            cur.execute("""
                SELECT quantity, unit_price FROM po_line_items
                WHERE po_id = %s AND ingredient_id = %s
            """, (po_id, ing_id))
            line_item = cur.fetchone()
            assert line_item is not None
            qty, price = line_item

            # Allow small float rounding differences
            assert abs(float(qty) - 60.0) < 0.1
            assert float(price) == 10.00
