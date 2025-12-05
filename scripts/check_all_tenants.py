#!/usr/bin/env python3
"""
Check ALL tenants and their data
"""
import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Get ALL tenants
cur.execute("SELECT id, name, created_at FROM tenants ORDER BY created_at DESC")
tenants = cur.fetchall()

print("=" * 80)
print(f"FOUND {len(tenants)} TENANTS")
print("=" * 80)

for tenant_id, name, created_at in tenants:
    print(f"\n{'='*80}")
    print(f"Tenant: {name} ({tenant_id})")
    print(f"Created: {created_at}")
    print(f"{'='*80}")

    # Get user
    cur.execute("SELECT email FROM users WHERE tenant_id = %s", (tenant_id,))
    users = cur.fetchall()
    print(f"Users: {[u[0] for u in users]}")

    # Get menu items
    cur.execute("SELECT name FROM menu_items WHERE tenant_id = %s LIMIT 10", (tenant_id,))
    items = cur.fetchall()
    print(f"Menu Items: {[i[0] for i in items]}")

    # Get forecasts count
    cur.execute("SELECT COUNT(*) FROM forecasts WHERE tenant_id = %s", (tenant_id,))
    forecast_count = cur.fetchone()[0]
    print(f"Forecasts: {forecast_count}")

conn.close()
