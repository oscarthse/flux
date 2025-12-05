#!/usr/bin/env python3
"""
Check forecasts for tenant 'resta'
"""
import psycopg2
import os
from datetime import date

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

tenant_id = "0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3" # resta

print(f"Checking forecasts for tenant: {tenant_id}")
print(f"Current Date: {date.today()}")

cur.execute("""
    SELECT
        mi.name,
        f.forecast_date,
        f.predicted_quantity
    FROM forecasts f
    JOIN menu_items mi ON f.menu_item_id = mi.id
    WHERE f.tenant_id = %s
    ORDER BY f.forecast_date DESC
    LIMIT 20
""", (tenant_id,))

rows = cur.fetchall()
if not rows:
    print("NO FORECASTS FOUND!")
else:
    print(f"Found {len(rows)} forecasts (showing top 20):")
    for row in rows:
        print(f"- {row[0]} ({row[1]}): {row[2]}")

conn.close()
