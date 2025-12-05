#!/usr/bin/env python3
"""
Simple cleanup: Delete all menu-related data for tenant
"""
import sys
import os
import psycopg2

sys.path.append(os.getcwd())

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def simple_cleanup():
    print("=" * 80)
    print("SIMPLE CLEANUP: Deleting all menu-related data")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get tenant
    cur.execute("SELECT id, name FROM tenants ORDER BY created_at DESC LIMIT 1")
    tenant_id, tenant_name = cur.fetchone()
    print(f"\nTenant: {tenant_name} ({tenant_id})")

    # Delete in dependency order
    tables = [
        "forecasts",
        "order_line_items",
        "sales_orders",
        "recipes",
        "menu_items",
        "inventory_batches",
        "ingredients"
    ]

    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        print(f"  Deleted {cur.rowcount} rows from {table}")

    conn.commit()
    conn.close()

    print("\n✅ Cleanup complete!")
    print("\nNext steps:")
    print("  1. Go to /ingestion/upload")
    print("  2. Upload files in order: ingredients → menu → recipes → sales")
    print("  3. Dashboard should populate automatically")

if __name__ == "__main__":
    simple_cleanup()
