import pytest
from lib.flux_lib.db import get_db_connection
from uuid import uuid4

def test_tenant_isolation(tenant_id, other_tenant_id):
    """
    Verify that data inserted by one tenant is NOT visible to another.
    """
    # 1. Insert data as Tenant A
    item_name = f"Burger {uuid4()}"
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO menu_items (name, price, tenant_id)
                VALUES (%s, 10.00, %s)
            """, (item_name, tenant_id))

    # 2. Try to read as Tenant B (Should see nothing)
    with get_db_connection(tenant_id=other_tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM menu_items WHERE name = %s", (item_name,))
            results = cur.fetchall()
            assert len(results) == 0, "RLS FAILURE: Tenant B saw Tenant A's data!"

    # 3. Read as Tenant A (Should see it)
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM menu_items WHERE name = %s", (item_name,))
            results = cur.fetchall()
            assert len(results) == 1, "Tenant A could not see their own data."

def test_rls_enforcement_error():
    """
    Verify that querying without setting a tenant_id returns empty results (or fails depending on config).
    Our policy says: USING (tenant_id = current_setting(...))
    If current_setting is null, uuid cast might fail or return null.
    If null, tenant_id = NULL is false (unless tenant_id is null, which is not allowed).
    So it should return 0 rows.
    """
    # We manually connect without the context manager that sets the variable
    import psycopg2
    import os
    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://flux_app:flux_pass@localhost:5432/flux"))
    try:
        with conn.cursor() as cur:
            # Try to read all menu items
            cur.execute("SELECT * FROM menu_items")
            results = cur.fetchall()
            # Should be empty because RLS policy evaluates to False/Null
            assert len(results) == 0, "Security Risk: Raw connection saw data without tenant context!"
    finally:
        conn.close()
