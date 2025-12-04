import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from lib.flux_lib.db import get_db_connection
from uuid import uuid4
from datetime import datetime

client = TestClient(app)

def test_triage_list(tenant_id):
    """
    Test that the triage list endpoint returns the correct HTML with pending items.
    """
    # 1. Setup: Insert a pending triage item
    external_id = "GHOST_123"
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO triage_items (tenant_id, external_id, external_name, source, status)
                VALUES (%s, %s, 'Ghost Burger', 'square', 'pending')
            """, (tenant_id, external_id))

    # 2. Action: GET /triage/list
    response = client.get("/triage/list", headers={"X-Tenant-ID": tenant_id})

    # 3. Assert
    assert response.status_code == 200
    assert "Ghost Burger" in response.text
    assert "GHOST_123" in response.text

def test_triage_ignore_action(tenant_id):
    """
    Test that the 'ignore' action updates the item status.
    """
    # 1. Setup
    item_id = str(uuid4())
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO triage_items (id, tenant_id, external_id, external_name, source, status)
                VALUES (%s, %s, %s, 'Ignore Me', 'square', 'pending')
            """, (item_id, tenant_id, "IGNORE_999"))

    # 2. Action: POST /triage/resolve (action=ignore)
    response = client.post(
        "/triage/resolve",
        data={"triage_id": item_id, "action": "ignore"},
        headers={"X-Tenant-ID": tenant_id}
    )

    # 3. Assert
    assert response.status_code == 200

    # Verify DB update
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM triage_items WHERE id = %s", (item_id,))
            row = cur.fetchone()
            assert row[0] == "ignored"
