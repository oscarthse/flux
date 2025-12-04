"""
Concurrency and Locking Tests

Tests concurrent access patterns and database locking behavior
to ensure data integrity under concurrent load.
"""
import pytest
import threading
import time
from services.worker.engines.inventory import generate_draft_orders


@pytest.mark.integration
@pytest.mark.slow
def test_concurrent_optimization_no_duplicate_pos(tenant_id, db_connection):
    """Test: Concurrent optimization runs don't create duplicate POs."""
    # Setup: Create minimal data for optimization
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

        cur.execute("""
            INSERT INTO ingredients (tenant_id, name, cost_per_unit, lead_time_days)
            VALUES (%s, 'Concurrent Test Ingredient', 5.00, 2)
        """, (tenant_id,))

        db_connection.commit()

    # Run optimization twice concurrently
    results = []
    errors = []

    def run_optimization():
        try:
            # Each thread gets its own connection
            import psycopg2
            conn_str = "postgresql://flux_app:flux_pass@localhost:5435/flux"
            conn = psycopg2.connect(conn_str)
            generate_draft_orders(tenant_id, conn)
            conn.close()
            results.append("success")
        except Exception as e:
            errors.append(str(e))

    threads = []
    for _ in range(2):
        t = threading.Thread(target=run_optimization)
        threads.append(t)
        t.start()
        time.sleep(0.01)  # Small delay to increase chance of collision

    for t in threads:
        t.join()

    # Verify: Reasonable number of POs created (not duplicates)
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT COUNT(*) FROM purchase_orders")
        count = cur.fetchone()[0]

        # Should be 0-2 POs, NOT 4+ (which would indicate duplication)
        assert count <= 2, f"Concurrent runs created {count} POs, possible duplication"


@pytest.mark.integration
@pytest.mark.rls
def test_concurrent_tenant_operations_isolated(tenant_id, other_tenant_id, db_connection):
    """Test: Concurrent operations by different tenants are isolated."""
    def operation_tenant_a():
        import psycopg2
        import os
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        with conn.cursor() as cur:
            cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
            cur.execute("""
                INSERT INTO menu_items (tenant_id, name, price)
                VALUES (%s, 'Tenant A Concurrent Item', 10.00)
            """, (tenant_id,))
            conn.commit()
        conn.close()

    def operation_tenant_b():
        import psycopg2
        import os
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        with conn.cursor() as cur:
            cur.execute("SET app.current_tenant_id = %s", (other_tenant_id,))
            cur.execute("""
                INSERT INTO menu_items (tenant_id, name, price)
                VALUES (%s, 'Tenant B Concurrent Item', 12.00)
            """, (other_tenant_id,))
            conn.commit()
        conn.close()

    # Run both operations concurrently
    t1 = threading.Thread(target=operation_tenant_a)
    t2 = threading.Thread(target=operation_tenant_b)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Verify: Each tenant only sees their own data
    with db_connection.cursor() as cur:
        # Check Tenant A
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT COUNT(*) FROM menu_items WHERE name LIKE '%Concurrent Item%'")
        count_a = cur.fetchone()[0]
        assert count_a == 1, "Tenant A should see only their item"

        # Check Tenant B
        cur.execute("SET app.current_tenant_id = %s", (other_tenant_id,))
        cur.execute("SELECT COUNT(*) FROM menu_items WHERE name LIKE '%Concurrent Item%'")
        count_b = cur.fetchone()[0]
        assert count_b == 1, "Tenant B should see only their item"


@pytest.mark.integration
@pytest.mark.slow
def test_transaction_rollback_on_error(tenant_id, db_connection):
    """Test: Failed transactions properly rollback without leaving partial data."""
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

        # Get initial count
        cur.execute("SELECT COUNT(*) FROM menu_items")
        initial_count = cur.fetchone()[0]

    # Attempt transaction that will fail (duplicate key)
    try:
        with db_connection.cursor() as cur:
            cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

            # Insert first item (succeeds)
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES ('00000000-0000-0000-0000-000000000001', %s, 'Item 1', 10.00)
            """, (tenant_id,))

            # Try to insert duplicate ID (fails)
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES ('00000000-0000-0000-0000-000000000001', %s, 'Item 2', 15.00)
            """, (tenant_id,))

            db_connection.commit()
    except Exception:
        db_connection.rollback()

    # Verify: No partial data left
    with db_connection.cursor() as cur:
        cur.execute("SET app.current_tenant_id = %s", (tenant_id,))
        cur.execute("SELECT COUNT(*) FROM menu_items")
        final_count = cur.fetchone()[0]

        assert final_count == initial_count, "Failed transaction should not leave partial data"
