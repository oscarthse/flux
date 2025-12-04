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
    assert "Demand Forecasting" in response.text
    assert "Chart Burger" in response.text


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
    response = client.get(f"/analytics/forecast-data?menu_item_id={item_id}", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    data = json_response["data"]

    assert "dates" in data
    assert "quantities" in data
    assert data["quantities"][0] == 25.0

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
    response = client.get(f"/analytics/forecast-table?menu_item_id={item_id}", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    assert "<table" in response.text
    assert "30.0" in response.text
