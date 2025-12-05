import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_db_connection():
    """
    Fixture that returns a mock database connection and cursor.
    Handles the context manager pattern: with conn.cursor() as cur:
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Setup cursor context manager: with conn.cursor() as cur
    # conn.cursor() returns a mock object whose __enter__ returns the actual mock_cursor
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    return mock_conn, mock_cursor

@pytest.fixture
def mock_prophet():
    """
    Fixture that mocks the Prophet class.
    """
    with patch("services.worker.engines.forecasting.prophet_model.Prophet") as mock:
        yield mock

@pytest.fixture
def tenant_id():
    """
    Fixture that creates a temporary tenant for integration tests.
    """
    import psycopg2
    import os
    from uuid import uuid4

    DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True

    tid = str(uuid4())

    try:
        with conn.cursor() as cur:
            # Create tenant
            cur.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s)",
                (tid, f"Test Tenant {tid}")
            )

        yield tid

    finally:
        try:
            with conn.cursor() as cur:
                # Cleanup (Cascade delete handles related data usually, but let's be safe)
                # Note: If we have foreign keys with CASCADE, deleting tenant is enough.
                # If not, we might need to delete related data first.
                # Assuming CASCADE for now based on schema.
                cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))
        except Exception:
            pass
        finally:
            conn.close()

@pytest.fixture
def auth_token(tenant_id):
    """
    Fixture that generates a valid session token for the test tenant.
    """
    from services.api.security import sign_session_cookie
    from uuid import uuid4

    user_id = str(uuid4())
    session_data = {"user_id": user_id, "tenant_id": tenant_id}
    return sign_session_cookie(session_data)

@pytest.fixture
def client(auth_token):
    """
    Fixture that returns an authenticated TestClient.
    """
    from fastapi.testclient import TestClient
    from services.api.main import app

    client = TestClient(app)
    client.cookies.set("flux_session", auth_token)
    return client
