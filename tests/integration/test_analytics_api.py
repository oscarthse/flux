import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from lib.flux_lib.db import get_db_connection
from uuid import uuid4
from datetime import date, timedelta

client = TestClient(app)

def test_forecast_dashboard_render(tenant_id):
    """
    Test that the dashboard renders with the item selector.
    """
    # 1. Setup: Create a menu item
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Chart Burger', 10.00)
            """, (str(uuid4()), tenant_id))

    # 2. Action: GET /analytics/forecasts
    response = client.get("/analytics/forecasts", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    assert "Forecasting Dashboard" in response.text
    assert "Chart Burger" in response.text

def test_forecast_chart_data(tenant_id):
    """
    Test that the chart endpoint returns valid HTML/JS with data.
    """
    # 1. Setup: Item + Sales + Forecast
    item_id = str(uuid4())
    today = date.today()

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Data Burger', 10.00)
            """, (item_id, tenant_id))

            # Sale yesterday
            yesterday = today - timedelta(days=1)
            order_id = str(uuid4())
            cur.execute("""
                INSERT INTO sales_orders (id, tenant_id, external_id, timestamp, total_amount)
                VALUES (%s, %s, 'ORD_CHART', %s, 10.00)
            """, (order_id, tenant_id, yesterday))
            cur.execute("""
                INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
                VALUES (%s, %s, %s, 5, 10.00)
            """, (tenant_id, order_id, item_id))

            # Forecast tomorrow
            tomorrow = today + timedelta(days=1)
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity, confidence_interval_lower, confidence_interval_upper)
                VALUES (%s, %s, %s, 10.0, 8.0, 12.0)
            """, (tenant_id, item_id, tomorrow))

    # 2. Action: GET /analytics/forecast-chart
    response = client.get(f"/analytics/forecast-chart?item_selector={item_id}", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    # Check for Chart.js data injection
    assert "Data Burger" in response.text
    assert str(yesterday) in response.text # Date label
    assert "5.0" in response.text # Actuals
    assert "10.0" in response.text # Forecast

def test_forecast_data_json(tenant_id):
    """
    Test that the forecast data endpoint returns valid JSON.
    """
    # 1. Setup
    item_id = str(uuid4())
    today = date.today()

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'JSON Burger', 10.00)
            """, (item_id, tenant_id))

            # Insert forecast
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 25.0)
            """, (tenant_id, item_id, today))

    # 2. Action
    response = client.get(f"/analytics/forecast-data?item_selector={item_id}", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    data = response.json()
    assert "dates" in data
    assert "actuals" in data
    assert "forecasts" in data
    assert data["forecasts"][0] == 25.0

def test_forecast_table_html(tenant_id):
    """
    Test that the forecast table endpoint returns HTML fragment.
    """
    # 1. Setup
    item_id = str(uuid4())
    today = date.today()

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Table Burger', 10.00)
            """, (item_id, tenant_id))

            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 30.0)
            """, (tenant_id, item_id, today))

    # 2. Action
    response = client.get(f"/analytics/forecast-table?item_selector={item_id}", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    assert "<table" in response.text
    assert "30.0" in response.text
