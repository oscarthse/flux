import pytest
from datetime import date, timedelta
from uuid import uuid4
from services.worker.engines.forecasting import ForecastingEngine
from lib.flux_lib.db import get_db_connection

def test_forecasting_logic(tenant_id):
    """
    Test that the forecasting engine correctly calculates the moving average.
    """
    # 1. Setup: Create Menu Item and Historical Sales
    menu_item_id = str(uuid4())
    today = date.today()

    # We need sales history for the Moving Average model (default window 28 days)
    # Let's simulate a steady 10 items per day for the last 30 days

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Create Menu Item
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Forecast Burger', 10.00)
            """, (menu_item_id, tenant_id))

            # Insert Sales for last 30 days
            for i in range(30):
                sale_date = today - timedelta(days=i)
                order_id = str(uuid4())
                cur.execute("""
                    INSERT INTO sales_orders (id, tenant_id, external_id, timestamp, total_amount)
                    VALUES (%s, %s, %s, %s, 100.00)
                """, (order_id, tenant_id, f"ORD_{i}", sale_date))

                cur.execute("""
                    INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
                    VALUES (%s, %s, %s, 10, 10.00)
                """, (tenant_id, order_id, menu_item_id))

    # 2. Action: Generate Forecasts
    with get_db_connection(tenant_id=tenant_id) as conn:
        # Initialize engine with moving_average model
        engine = ForecastingEngine(tenant_id, conn, model_name='moving_average')
        # Generate for next 7 days
        engine.generate_forecasts(forecast_days=7)

    # 3. Assert
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Check forecast for tomorrow
            tomorrow = today + timedelta(days=1)
            cur.execute("""
                SELECT predicted_quantity
                FROM forecasts
                WHERE tenant_id = %s AND menu_item_id = %s AND forecast_date = %s
            """, (tenant_id, menu_item_id, tomorrow))

            row = cur.fetchone()
            assert row is not None
            predicted = float(row[0])

            # Expected Avg: 10.0 (since all history is 10)
            assert predicted == 10.0
