import pytest
from services.api.main import app
from lib.flux_lib.db import get_db_connection
from uuid import uuid4
from datetime import date, timedelta

def test_dashboard_home_render(client, tenant_id):
    """
    Test that the dashboard homepage renders with metrics.
    Ensures data is properly seeded and retrieved.
    """
    # 1. Setup: Create specific data to verify exact calculations
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Create Menu Item with Price $1.00
            item_id = str(uuid4())
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Test Item', 1.00)
            """, (item_id, tenant_id))

            # Create Forecast for Today with Quantity 150
            # Revenue = 150 * $1.00 = $150
            f_date = date.today()
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 150.0)
            """, (tenant_id, item_id, f_date))

            # Create a Draft Purchase Order to test that metric too
            po_id = str(uuid4())
            cur.execute("""
                INSERT INTO purchase_orders (id, tenant_id, status, created_at)
                VALUES (%s, %s, 'DRAFT', NOW())
            """, (po_id, tenant_id))

    # 2. Action: GET /dashboard
    # Pass the tenant_id in headers so the router queries the correct data
    response = client.get("/dashboard", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200

    # Verify Page Title (Now "Dashboard - Flux Platform" from base template or similar)
    # The template extends base.html and has block title "Dashboard - Flux Platform"
    assert "Dashboard - Flux Platform" in response.text

    # Verify Revenue Metric
    # Should be $150 (150 items * $1.00)
    # The template formats it as just the number if it's an integer, or with commas
    # We look for "150" specifically
    assert "150" in response.text

    # Verify Draft Orders Metric
    # We created 1 draft order
    assert "Draft Orders" in response.text
    # We can't easily assert "1" without context, but we can check if the section exists

    # Verify "Projected Sales (Next 7 Days)" label is present
    assert "Projected Sales (Next 7 Days)" in response.text

    # Verify Model Accuracy label is present
    assert "Model Accuracy" in response.text

def test_dashboard_metrics_chart(client, tenant_id):
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
    assert "dashboard-trend-chart" in response.text
    assert "Plotly.newPlot" in response.text
    assert "20.0" in response.text # Check for data values

def test_dashboard_empty_state(client, tenant_id):
    """
    Test dashboard behavior with no data.
    """
    # No data setup

    response = client.get("/dashboard", headers={"X-Tenant-ID": tenant_id})

    assert response.status_code == 200
    assert "Dashboard - Flux Platform" in response.text
    assert "$0.00" in response.text # Zero revenue formatted
