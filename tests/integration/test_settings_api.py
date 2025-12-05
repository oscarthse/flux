import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import db_service
import uuid

client = TestClient(app)

@pytest.fixture
def setup_settings_data():
    tenant_id = str(uuid.uuid4())

    # Create Tenant
    with db_service.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", (tenant_id, "Settings Test Tenant"))

            # Create User
            user_id = str(uuid.uuid4())
            email = f"settings_test_{user_id}@example.com"
            cur.execute("INSERT INTO users (id, email, password_hash, tenant_id) VALUES (%s, %s, %s, %s)",
                        (user_id, email, "hash", tenant_id))

            conn.commit()

    return tenant_id, user_id

def test_get_settings_creates_defaults(setup_settings_data):
    tenant_id, user_id = setup_settings_data

    # Mock Session
    from services.api import security
    token = security.sign_session_cookie({"user_id": user_id, "tenant_id": tenant_id})
    client.cookies.set("flux_session", token)

    # First call should create defaults
    response = client.get("/settings/")
    assert response.status_code == 200
    assert "Settings Control Panel" in response.text
    assert "prophet" in response.text # Default model
    assert "20.0" in response.text # Default safety stock

def test_update_settings(setup_settings_data):
    tenant_id, user_id = setup_settings_data

    # Mock Session
    from services.api import security
    token = security.sign_session_cookie({"user_id": user_id, "tenant_id": tenant_id})
    client.cookies.set("flux_session", token)

    # Ensure defaults exist
    client.get("/settings/")

    # Update a setting
    response = client.patch(
        "/settings/update",
        data={"field": "safety_stock_buffer_percent", "value": "50.0"}
    )
    assert response.status_code == 200
    assert "Saved" in response.text

    # Verify persistence
    response = client.get("/settings/")
    assert "50.0" in response.text

def test_update_invalid_field(setup_settings_data):
    tenant_id, user_id = setup_settings_data

    # Mock Session
    from services.api import security
    token = security.sign_session_cookie({"user_id": user_id, "tenant_id": tenant_id})
    client.cookies.set("flux_session", token)

    response = client.patch(
        "/settings/update",
        data={"field": "invalid_field", "value": "100"}
    )
    assert response.status_code == 400
    assert "Invalid field" in response.text
