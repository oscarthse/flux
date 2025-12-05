#!/usr/bin/env python3
"""
Debug Menu Engineering for Classic Burger
"""
import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

tenant_id = "0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3" # resta
item_name = "Classic Burger"

print(f"Debugging Menu Engineering for: {item_name}")

# 1. Get Menu Item ID and Price
cur.execute("SELECT id, price FROM menu_items WHERE name = %s AND tenant_id = %s", (item_name, tenant_id))
row = cur.fetchone()
if not row:
    print("Item not found!")
    exit()
item_id, price = row
print(f"ID: {item_id}, Price: {price}")

# 2. Get Recipe and Ingredient Costs
print("\nRecipe Breakdown:")
cur.execute("""
    SELECT
        i.name,
        r.quantity,
        i.unit,
        i.cost_per_unit,
        (r.quantity * i.cost_per_unit) as cost
    FROM recipes r
    JOIN ingredients i ON r.ingredient_id = i.id
    WHERE r.menu_item_id = %s
""", (item_id,))

total_cogs = 0
for row in cur.fetchall():
    print(f"- {row[0]}: {row[1]} {row[2]} @ ${row[3]:.2f}/{row[2]} = ${row[4]:.2f}")
    total_cogs += float(row[4])

print(f"\nTotal COGS: ${total_cogs:.2f}")
print(f"Margin: ${float(price) - total_cogs:.2f}")

# 3. Get Sales Volume
cur.execute("""
    SELECT SUM(oli.quantity)
    FROM order_line_items oli
    JOIN sales_orders so ON oli.order_id = so.id
    WHERE oli.menu_item_id = %s
      AND so.timestamp >= NOW() - INTERVAL '30 days'
""", (item_id,))
volume = cur.fetchone()[0]
print(f"\nSales Volume (30 days): {volume}")

conn.close()
