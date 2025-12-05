import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import db_service
from unittest.mock import MagicMock, patch

client = TestClient(app)

@pytest.fixture
def mock_db_connection():
    with patch("services.api.database.db_service.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        yield mock_cursor

@pytest.fixture
def mock_tenant_context():
    with patch("services.api.routers.menu.tenant_context") as mock_ctx:
        mock_ctx.get.return_value = "test-tenant-id"
        yield mock_ctx

@pytest.fixture
def mock_auth():
    with patch("services.api.security.verify_session_cookie") as mock_verify:
        mock_verify.return_value = {"tenant_id": "test-tenant-id", "user_id": "test-user-id"}
        yield mock_verify

def test_get_menu_details_success(mock_db_connection, mock_tenant_context, mock_auth):
    # Mock DB responses
    # 1. Basic Info
    mock_db_connection.fetchone.side_effect = [
        ("test@example.com",), # Middleware: User email
        ("Test Restaurant",), # Middleware: Tenant name
        ("Test Burger", 15.0, "Entree"), # item_row
        (100, 1500.0, "Friday"), # sales_row (first call)
        (100, 1500.0), # totals (second call)
    ]

    # 3. Recipe & Ingredients (fetchall)
    mock_db_connection.fetchall.return_value = [
        ("ing-1", "Beef Patty", 1.0, "patty", 2.0),
        ("ing-2", "Bun", 1.0, "bun", 0.5)
    ]

    # Mock Inventory Engine
    with patch("services.api.routers.menu.calculate_inventory_health") as mock_calc:
        m1 = MagicMock()
        m1.ingredient_id = "ing-1"
        m1.name = "Beef Patty"
        m1.current_stock = 10
        m1.status = "critical"
        m1.days_until_runout = 1.2
        m1.usage_explanation = "Used in Test Burger"
        m1.risk_explanation = "Revenue risk $500"

        m2 = MagicMock()
        m2.ingredient_id = "ing-2"
        m2.name = "Bun"
        m2.current_stock = 50
        m2.status = "healthy"
        m2.days_until_runout = 10.0
        m2.usage_explanation = "Used in Test Burger"
        m2.risk_explanation = "No risk"

        mock_calc.return_value = [m1, m2]

        client.cookies.set("flux_session", "dummy-token")
        response = client.get("/menu/test-item-id")

        assert response.status_code == 200
        assert "Test Burger" in response.text
        assert "Beef Patty" in response.text
        assert "Critical (1.2 days)" in response.text
        assert "This ingredient is Critical because Used in Test Burger. Revenue risk $500" in response.text
