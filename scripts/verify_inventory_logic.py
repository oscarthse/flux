#!/usr/bin/env python3
"""
Verify inventory logic for tenant 'resta'
"""
import psycopg2
import os
from services.worker.engines.inventory import calculate_inventory_health

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
conn = psycopg2.connect(DB_URL)

tenant_id = "0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3" # resta

print(f"Checking inventory for tenant: {tenant_id}")

try:
    health_data = calculate_inventory_health(tenant_id, conn)
    print(f"Found {len(health_data)} inventory items.")
    for item in health_data[:5]:
        print(f"- {item.name}: Stock={item.current_stock}, Burn={item.burn_rate:.2f}, Days={item.days_until_runout:.1f}, Status={item.status}")
except Exception as e:
    print(f"Error: {e}")

conn.close()
