import pytest
from datetime import date, timedelta
from uuid import uuid4
from services.worker.engines.forecasting import generate_forecast
from lib.flux_lib.db import get_db_connection

def test_forecasting_logic(tenant_id):
    """
    Test that the forecasting engine correctly calculates the 4-week moving average.
    """
    # 1. Setup: Create Menu Item and Historical Sales
    menu_item_id = str(uuid4())
    today = date.today()
    target_dow = (today + timedelta(days=1)).weekday() # Forecast for tomorrow

    # We need to simulate sales on the SAME day of week for the past 4 weeks.
    # Let's say tomorrow is Friday. We need sales for last 4 Fridays.

    # Calculate dates for last 4 weeks (same DOW)
    # Start from tomorrow, go back 1 week, 2 weeks, etc.
    tomorrow = today + timedelta(days=1)
    past_dates = [tomorrow - timedelta(weeks=i) for i in range(1, 5)]

    # Sales quantities: 10, 12, 10, 8 -> Avg = 10.0
    quantities = [10, 12, 10, 8]

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Create Menu Item
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Forecast Burger', 10.00)
            """, (menu_item_id, tenant_id))

            # Insert Sales
            for d, qty in zip(past_dates, quantities):
                # Create Order
                order_id = str(uuid4())
                cur.execute("""
                    INSERT INTO sales_orders (id, tenant_id, external_id, timestamp, total_amount)
                    VALUES (%s, %s, %s, %s, 100.00)
                """, (order_id, tenant_id, f"ORD_{d}", d))

                # Create Line Item
                cur.execute("""
                    INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
                    VALUES (%s, %s, %s, %s, 10.00)
                """, (tenant_id, order_id, menu_item_id, qty))

    # 2. Action: Generate Forecast for Tomorrow
    with get_db_connection(tenant_id=tenant_id) as conn:
        generate_forecast(tenant_id, tomorrow, conn)

    # 3. Assert
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT predicted_quantity, confidence_interval_lower, confidence_interval_upper
                FROM forecasts
                WHERE tenant_id = %s AND menu_item_id = %s AND forecast_date = %s
            """, (tenant_id, menu_item_id, tomorrow))

            row = cur.fetchone()
            assert row is not None
            predicted = float(row[0])

            # Expected Avg: (10+12+10+8)/4 = 10.0
            assert predicted == 10.0
            assert float(row[1]) == 8.0  # Lower bound (0.8 * 10)
            assert float(row[2]) == 12.0 # Upper bound (1.2 * 10)
