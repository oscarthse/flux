import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import db_service
import uuid
from datetime import date, timedelta

client = TestClient(app)

@pytest.fixture
def setup_menu_data():
    tenant_id = str(uuid.uuid4())

    # Create Tenant
    with db_service.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", (tenant_id, "Test Tenant"))

            # Create User
            user_id = str(uuid.uuid4())
            email = f"test_{user_id}@example.com"
            cur.execute("INSERT INTO users (id, email, password_hash, tenant_id) VALUES (%s, %s, %s, %s)",
                        (user_id, email, "hash", tenant_id))

            # Create Ingredient
            ing_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO ingredients (id, tenant_id, name, unit, cost_per_unit, lead_time_days)
                VALUES (%s, %s, 'Test Flour', 'kg', 2.50, 2)
            """, (ing_id, tenant_id))

            # Add Stock
            cur.execute("""
                INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity, received_at, expires_at)
                VALUES (%s, %s, %s, 100, 100, CURRENT_DATE, CURRENT_DATE + 30)
            """, (str(uuid.uuid4()), tenant_id, ing_id))

            # Create Menu Item
            menu_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price, category)
                VALUES (%s, %s, 'Test Pizza', 15.00, 'Mains')
            """, (menu_id, tenant_id))

            # Create Recipe
            cur.execute("""
                INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
                VALUES (%s, %s, %s, 0.5)
            """, (tenant_id, menu_id, ing_id))

            # Create Sales (L30D)
            order_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO sales_orders (id, tenant_id, timestamp, total_amount)
                VALUES (%s, %s, NOW(), 15.00)
            """, (order_id, tenant_id))

            cur.execute("""
                INSERT INTO order_line_items (id, tenant_id, order_id, menu_item_id, quantity, price_at_order)
                VALUES (%s, %s, %s, %s, 1, 15.00)
            """, (str(uuid.uuid4()), tenant_id, order_id, menu_id))

            # Create Forecast (Next 7 Days)
            for i in range(7):
                forecast_date = date.today() + timedelta(days=i)
                cur.execute("""
                    INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                    VALUES (%s, %s, %s, 10.0)
                """, (tenant_id, menu_id, forecast_date))

            conn.commit()

    return tenant_id, user_id, menu_id, ing_id

def test_menu_registry_access(setup_menu_data):
    tenant_id, user_id, _, _ = setup_menu_data

    # Mock Session
    from services.api import security
    token = security.sign_session_cookie({"user_id": user_id, "tenant_id": tenant_id})
    client.cookies.set("flux_session", token)

    response = client.get("/menu/")
    assert response.status_code == 200
    assert "Menu Registry" in response.text
    assert "Test Pizza" in response.text

def test_menu_detail_panel(setup_menu_data):
    tenant_id, user_id, menu_id, ing_id = setup_menu_data

    # Mock Session
    from services.api import security
    token = security.sign_session_cookie({"user_id": user_id, "tenant_id": tenant_id})
    client.cookies.set("flux_session", token)

    response = client.get(f"/menu/{menu_id}")
    assert response.status_code == 200

    # Check Basic Info
    assert "Test Pizza" in response.text
    assert "$15.00" in response.text

    # Check Sales Stats
    assert "Units Sold (30d)" in response.text

    # Check Ingredient Audit
    assert "Test Flour" in response.text
    assert "0.5 kg" in response.text
    assert "Healthy" in response.text # Should be healthy as we have 100kg stock and low usage
