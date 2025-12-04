from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from lib.flux_lib.db import get_db_connection

def generate_draft_orders(tenant_id: str, conn=None):
    """
    Generates draft purchase orders based on (R, s) policy using forecasts.
    s (Reorder Point) = (Daily Forecast * Lead Time) + Safety Stock
    R (Order Up-To) = s + (Daily Forecast * Review Period)
    """
    if conn is None:
        with get_db_connection() as conn:
            return generate_draft_orders(tenant_id, conn)

    try:
        with conn.cursor() as cur:
            # 1. Fetch Ingredients and their current stock
            cur.execute("""
                SELECT
                    i.id, i.name, i.lead_time_days, i.cost_per_unit,
                    COALESCE(SUM(ib.remaining_quantity), 0) as current_stock
                FROM ingredients i
                LEFT JOIN inventory_batches ib ON i.id = ib.ingredient_id AND ib.remaining_quantity > 0
                WHERE i.tenant_id = %s
                GROUP BY i.id
            """, (tenant_id,))
            ingredients = cur.fetchall()

            # 2. Calculate Forecasted Usage per Ingredient for the next 7 days (avg daily)
            # We use the next 7 days forecast to estimate "Daily Forecast"
            cur.execute("""
                SELECT
                    r.ingredient_id,
                    SUM(f.predicted_quantity * r.quantity) / 7 as avg_daily_usage
                FROM forecasts f
                JOIN recipes r ON f.menu_item_id = r.menu_item_id
                WHERE f.tenant_id = %s
                  AND f.forecast_date >= CURRENT_DATE
                  AND f.forecast_date < CURRENT_DATE + INTERVAL '7 days'
                GROUP BY r.ingredient_id
            """, (tenant_id,))
            usage_map = {row[0]: row[1] for row in cur.fetchall()}

            po_items = []

            for ing in ingredients:
                ing_id, name, lead_time, cost, current_stock = ing
                lead_time = float(lead_time or 2) # Default 2 days
                cost = float(cost or 0)
                current_stock = float(current_stock)

                # Get usage forecast (default to 0 if no forecast)
                daily_usage = float(usage_map.get(ing_id, 0))

                if daily_usage == 0:
                    continue

                # (R, s) Policy Calculation
                # Safety Stock = 50% of Lead Time Demand (Simple heuristic)
                safety_stock = daily_usage * lead_time * 0.5

                # s = Reorder Point
                s = (daily_usage * lead_time) + safety_stock

                # R = Order Up-To Level (Review Period = 3 days)
                review_period = 3
                R = s + (daily_usage * review_period)

                if current_stock < s:
                    order_qty = R - current_stock
                    if order_qty > 0:
                        po_items.append({
                            "ingredient_id": ing_id,
                            "quantity": round(order_qty, 2),
                            "unit_price": cost
                        })

            if not po_items:
                print(f"[Inventory] No items to order for tenant {tenant_id}.")
                return

            # 3. Create Draft Purchase Order
            # Check if there is already a draft PO for today
            cur.execute("""
                SELECT id FROM purchase_orders
                WHERE tenant_id = %s AND status = 'draft' AND created_at::date = CURRENT_DATE
            """, (tenant_id,))
            existing_po = cur.fetchone()

            if existing_po:
                po_id = existing_po[0]
            else:
                cur.execute("""
                    INSERT INTO purchase_orders (tenant_id, status, delivery_date)
                    VALUES (%s, 'draft', CURRENT_DATE + INTERVAL '2 days')
                    RETURNING id
                """, (tenant_id,))
                po_id = cur.fetchone()[0]

            # 4. Insert Line Items
            for item in po_items:
                cur.execute("""
                    INSERT INTO po_line_items (tenant_id, po_id, ingredient_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tenant_id, po_id, item["ingredient_id"], item["quantity"], item["unit_price"]))

            print(f"[Inventory] Generated Draft PO {po_id} with {len(po_items)} items.")

    except Exception as e:
        print(f"[Inventory] Error: {e}")
        raise
