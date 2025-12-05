import pytest
from datetime import date, timedelta
from uuid import uuid4

@pytest.mark.integration
def test_dashboard_metrics(client, tenant_a_id, db_connection, seed_data):
    """
    Test dashboard metrics calculation:
    1. Model Accuracy (WMAPE)
    2. Low Stock Alerts
    """
    menu_item_id = seed_data["menu_item_id"]
    ingredient_id = seed_data["ingredient_id"]

    # 1. Setup Data for WMAPE (Last 30 days)
    # Scenario:
    # - Day 1: Forecast 10, Actual 12 (Error 2)
    # - Day 2: Forecast 10, Actual 8  (Error 2)
    # Total Error: 4, Total Actual: 20 -> WMAPE = 4/20 = 0.2 -> Accuracy = 80%

    today = date.today()
    day1 = today - timedelta(days=2)
    day2 = today - timedelta(days=1)

    with db_connection.cursor() as cur:
        # Insert Sales (Actuals)
        # Order 1 on Day 1
        order_id_1 = str(uuid4())
        cur.execute("""
            INSERT INTO sales_orders (id, tenant_id, timestamp, total_amount)
            VALUES (%s, %s, %s, 15.00)
        """, (order_id_1, tenant_a_id, f"{day1} 12:00:00"))

        cur.execute("""
            INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
            VALUES (%s, %s, %s, 12, 15.00)
        """, (tenant_a_id, order_id_1, menu_item_id))

        # Order 2 on Day 2
        order_id_2 = str(uuid4())
        cur.execute("""
            INSERT INTO sales_orders (id, tenant_id, timestamp, total_amount)
            VALUES (%s, %s, %s, 15.00)
        """, (order_id_2, tenant_a_id, f"{day2} 12:00:00"))

        cur.execute("""
            INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
            VALUES (%s, %s, %s, 8, 15.00)
        """, (tenant_a_id, order_id_2, menu_item_id))

        # Insert Forecasts
        cur.execute("""
            INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
            VALUES
                (%s, %s, %s, 10.0),
                (%s, %s, %s, 10.0)
        """, (tenant_a_id, menu_item_id, day1, tenant_a_id, menu_item_id, day2))


        # 2. Setup Data for Low Stock Alert (Next 7 days)
        # Inventory: 10kg Beef (from seed_data)
        # Recipe: Burger needs 0.5kg Beef
        # Forecast: 25 Burgers tomorrow -> Needs 12.5kg Beef
        # Result: 10kg < 12.5kg -> Low Stock Alert!
        # Financial Impact: Missing 2.5kg * $10/kg = $25.00

        tomorrow = today + timedelta(days=1)
        cur.execute("""
            INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
            VALUES (%s, %s, %s, 25.0)
        """, (tenant_a_id, menu_item_id, tomorrow))

        db_connection.commit()

    # 3. Call API
    response = client.get("/dashboard/stats", headers={"X-Tenant-ID": tenant_a_id})
    assert response.status_code == 200
    data = response.json()

    # 4. Verify
    # Accuracy: 80.0%
    assert data["model_accuracy"] == 80.0

    # Low Stock: 1 ingredient (Beef)
    assert data["low_stock_alerts"] == 1

    # Financial Impact: $25.00
    assert data["financial_impact"] == 25.00
