#!/usr/bin/env python3
import psycopg2
import os
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT id FROM menu_items WHERE name = 'Classic Burger' AND tenant_id = '0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3'")
print(cur.fetchone()[0])
conn.close()
