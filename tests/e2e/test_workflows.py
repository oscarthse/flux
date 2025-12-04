"""
End-to-End Workflow Tests

Tests complete user workflows from start to finish,
including API endpoints, HTMX responses, and multi-step scenarios.
"""
import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from datetime import date, timedelta

client = TestClient(app)


@pytest.mark.e2e
@pytest.mark.slow
def test_full_inventory_workflow(tenant_id, db_connection):
    """
    Test: Full workflow from forecast → optimization → PO → approval

    Steps:
    1. Setup: Create ingredients, menu items, forecasts
    2. Trigger optimization via API
    3. Verify draft PO created
    4. Approve PO via API
    5. Verify status changed to 'ordered'
    """
    # Step 1: Setup test data
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

        # Create ingredient
        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days, unit)
            VALUES (%s, 'E2E Test Ingredient', 10.00, 2, 'kg')
            RETURNING id
        """, (tenant_id,))
        ing_id = cur.fetchone()[0]

        # Create menu item
        cur.execute("""
            INSERT INTO menu_items (tenant_id, name, price)
            VALUES (%s, 'E2E Test Dish', 20.00)
            RETURNING id
        """, (tenant_id,))
        menu_id = cur.fetchone()[0]

        # Create recipe
        cur.execute("""
            INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
            VALUES (%s, %s, %s, 2.0)
        """, (tenant_id, menu_id, ing_id))

        # Create forecasts (high demand for next 7 days)
        for i in range(7):
            forecast_date = date.today() + timedelta(days=i)
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 100.0)
            """, (tenant_id, menu_id, forecast_date))

        db_connection.commit()

    # Step 2: Trigger optimization via API
    response = client.post("/inventory/generate")
    assert response.status_code == 200, f"Optimization endpoint failed: {response.text}"

    # Step 3: Verify draft PO created
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT id FROM purchase_orders WHERE status = 'draft' LIMIT 1")
        result = cur.fetchone()
        assert result is not None, "Draft PO should be created after optimization"
        po_id = result[0]

    # Step 4: Approve PO
    response = client.post(f"/inventory/orders/{po_id}/approve")
    assert response.status_code == 200, f"Approve endpoint failed: {response.text}"

    # Step 5: Verify status changed to 'ordered'
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT status FROM purchase_orders WHERE id = %s", (po_id,))
        status = cur.fetchone()[0]
        assert status == "ordered", f"PO status should be 'ordered', got '{status}'"


@pytest.mark.e2e
def test_smart_order_dashboard_renders(tenant_id):
    """Test: Smart Order dashboard page loads successfully."""
    response = client.get("/inventory/smart-order")
    assert response.status_code == 200
    assert b"Smart Order" in response.content or b"Purchase Order" in response.content


@pytest.mark.e2e
def test_forecasting_dashboard_renders(tenant_id):
    """Test: Forecasting dashboard page loads successfully."""
    response = client.get("/analytics/forecasts")
    assert response.status_code == 200
    assert b"Forecast" in response.content or b"forecast" in response.content


@pytest.mark.e2e
@pytest.mark.integration
def test_htmx_partial_response_po_list(tenant_id, db_connection):
    """Test: HTMX endpoint returns proper HTML fragment for PO list."""
    # Setup: Create a draft PO
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("""
            INSERT INTO purchase_orders (tenant_id, status)
            VALUES (%s, 'draft')
            RETURNING id
        """, (tenant_id,))
        po_id = cur.fetchone()[0]
        db_connection.commit()

    # Trigger optimization (should return HTML fragment)
    response = client.post("/inventory/generate")

    # Verify: Response is HTML (not JSON)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")

    # Verify: Contains PO elements
    content = response.content.decode()
    assert "draft" in content.lower() or "po" in content.lower()


@pytest.mark.e2e
@pytest.mark.integration
def test_api_error_handling_invalid_po(tenant_id):
    """Test: API returns proper error for invalid PO ID."""
    fake_po_id = "00000000-0000-0000-0000-999999999999"
    response = client.post(f"/inventory/orders/{fake_po_id}/approve")

    # Should return 404 or error response
    assert response.status_code in [404, 500], "Should return error for non-existent PO"


@pytest.mark.e2e
@pytest.mark.slow
def test_multi_step_user_scenario(tenant_id, db_connection):
    """
    Test: Realistic user scenario with multiple steps

    Scenario:
    1. User views Smart Order dashboard (no POs initially)
    2. User clicks "Run Optimization Now"
    3. System generates POs based on forecasts
    4. User views updated PO list
    5. User approves a PO
    6. System updates PO status
    """
    # Step 1: View dashboard (initially empty)
    response = client.get("/inventory/smart-order")
    assert response.status_code == 200

    # Step 2 & 3: Trigger optimization
    # (Setup some forecasts first)
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days)
            VALUES (%s, 'Multi-step Test Ing', 5.00, 2)
            RETURNING id
        """, (tenant_id,))
        ing_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO menu_items (tenant_id, name, price)
            VALUES (%s, 'Multi-step Dish', 15.00)
            RETURNING id
        """, (tenant_id,))
        menu_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
            VALUES (%s, %s, %s, 1.0)
        """, (tenant_id, menu_id, ing_id))

        for i in range(7):
            forecast_date = date.today() + timedelta(days=i)
            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                VALUES (%s, %s, %s, 50.0)
            """, (tenant_id, menu_id, forecast_date))

        db_connection.commit()

    response = client.post("/inventory/generate")
    assert response.status_code == 200

    # Step 4: Verify PO exists
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT id FROM purchase_orders WHERE status = 'draft' LIMIT 1")
        result = cur.fetchone()
        assert result is not None, "PO should exist after optimization"
        po_id = result[0]

    # Step 5 & 6: Approve PO
    response = client.post(f"/inventory/orders/{po_id}/approve")
    assert response.status_code == 200

    # Final verification
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT status FROM purchase_orders WHERE id = %s", (po_id,))
        status = cur.fetchone()[0]
        assert status == "ordered", "Final PO status should be 'ordered'"
