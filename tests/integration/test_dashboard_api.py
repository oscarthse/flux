import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from lib.flux_lib.db import get_db_connection
from uuid import uuid4
from datetime import date, timedelta

client = TestClient(app)

def test_dashboard_home_render(tenant_id):
    """
    Test that the dashboard homepage renders with metrics.
    """
    # 1. Setup: Create some data to populate metrics
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Create Menu Item
            item_id = str(uuid4())
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Dash Burger', 15.00)
            """, (item_id, tenant_id))

            # Create Forecasts (1 day)
            # 10 items * $15 = $150
            f_date = date.today()
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 10.0)
            """, (tenant_id, item_id, f_date))


    # 2. Action: GET /dashboard
    response = client.get("/dashboard", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    assert "Flux Restaurant" in response.text
    assert "Revenue (Next 7 Days)" in response.text

    # Check if revenue calculation is present
    # $150 should be formatted as $150
    assert "150" in response.text



    # Check other cards
    assert "Model Accuracy" in response.text
    assert "Draft Orders" in response.text

def test_dashboard_metrics_chart(tenant_id):
    """
    Test that the metrics chart endpoint returns valid HTML.
    """
    # 1. Setup: Create forecast data for the chart
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            item_id = str(uuid4())
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Chart Item', 10.00)
            """, (item_id, tenant_id))

            # Insert forecasts for chart
            for i in range(5):
                f_date = date.today() + timedelta(days=i)
                cur.execute("""
                    INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                    VALUES (%s, %s, %s, 20.0)
                """, (tenant_id, item_id, f_date))

    # 2. Action: GET /dashboard/metrics-chart
    response = client.get("/dashboard/metrics-chart", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200

    # Check for chart elements
    assert "flex h-full" in response.text # Container
    assert "20" in response.text # Value label

    # Check Y-axis labels generation
    # Max value is 20, so Y-axis should cover it
    assert "text-xs text-slate-500" in response.text

def test_dashboard_empty_state(tenant_id):
    """
    Test dashboard behavior with no data.
    """
    # No data setup

    response = client.get("/dashboard", headers={"X-Tenant-ID": tenant_id})

    assert response.status_code == 200
    assert "$0" in response.text # Zero revenue
    assert "Orders (Next 7 Days)" not in response.text # Should be Revenue now
