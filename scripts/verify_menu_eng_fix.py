#!/usr/bin/env python3
"""
Verify Menu Engineering Fix
"""
import psycopg2
import os
from services.worker.engines.menu_analytics import calculate_menu_performance

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
conn = psycopg2.connect(DB_URL)

tenant_id = "0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3" # resta

print(f"Checking Menu Engineering for tenant: {tenant_id}")

try:
    items, metrics = calculate_menu_performance(tenant_id, 30, conn)
    print(f"Found {len(items)} items.")

    paella_found = False
    burger_found = False

    for item in items:
        if "Paella" in item.item_name:
            paella_found = True
            print(f"ERROR: Found {item.item_name} (Should NOT be here)")
        if "Burger" in item.item_name:
            burger_found = True
            # print(f"Found {item.item_name} (Correct)")

    if not paella_found:
        print("SUCCESS: Seafood Paella NOT found.")
    if burger_found:
        print("SUCCESS: Burgers found.")

except Exception as e:
    print(f"Error: {e}")

conn.close()
