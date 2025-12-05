#!/usr/bin/env python3
"""
Final verification: What's actually in the database?
"""
import sys
import os
import psycopg2

sys.path.append(os.getcwd())

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def verify_database_state():
    print("=" * 80)
    print("DATABASE STATE VERIFICATION")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get tenant
    cur.execute("SELECT id, name FROM tenants ORDER BY created_at DESC LIMIT 1")
    tenant_id, tenant_name = cur.fetchone()
    print(f"\nTenant: {tenant_name} ({tenant_id})")

    # Check each table
    tables = {
        "ingredients": "SELECT COUNT(*), STRING_AGG(name, ', ') FROM ingredients WHERE tenant_id = %s",
        "menu_items": "SELECT COUNT(*), STRING_AGG(name || ' (ext_id: ' || COALESCE(external_id, 'NULL') || ')', ', ') FROM menu_items WHERE tenant_id = %s",
        "recipes": "SELECT COUNT(*) FROM recipes WHERE tenant_id = %s",
        "sales_orders": "SELECT COUNT(*), MIN(timestamp::date), MAX(timestamp::date) FROM sales_orders WHERE tenant_id = %s",
        "inventory_batches": "SELECT COUNT(*), SUM(remaining_quantity) FROM inventory_batches WHERE tenant_id = %s",
        "forecasts": "SELECT COUNT(*), MIN(predicted_quantity), MAX(predicted_quantity), AVG(predicted_quantity) FROM forecasts WHERE tenant_id = %s"
    }

    for table, query in tables.items():
        cur.execute(query, (tenant_id,))
        result = cur.fetchone()
        print(f"\n{table}:")
        print(f"  {result}")

    # Show sample forecasts
    print("\n" + "=" * 80)
    print("SAMPLE FORECASTS (if any):")
    print("=" * 80)
    cur.execute("""
        SELECT mi.name, f.forecast_date, f.predicted_quantity
        FROM forecasts f
        JOIN menu_items mi ON f.menu_item_id = mi.id
        WHERE f.tenant_id = %s
        ORDER BY f.forecast_date, mi.name
        LIMIT 20
    """, (tenant_id,))

    for row in cur.fetchall():
        print(f"  {row}")

    conn.close()

if __name__ == "__main__":
    verify_database_state()
