#!/usr/bin/env python3
"""
PHASE 1: Database Integrity Audit
Checkpoint A: Schema Review - Foreign Keys
Checkpoint B: Data Isolation - Tenant ID columns
"""
import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("=" * 80)
print("PHASE 1A: FOREIGN KEY RELATIONSHIPS")
print("=" * 80)

# Get all foreign keys for critical tables
critical_tables = ['ingredients', 'menu_items', 'recipes', 'sales_orders', 'order_line_items', 'forecasts', 'inventory_batches']

for table in critical_tables:
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = %s
    """, (table,))

    fks = cur.fetchall()
    if fks:
        print(f"\n{table}:")
        for fk in fks:
            print(f"  {fk[1]} → {fk[2]}.{fk[3]}")
    else:
        print(f"\n{table}: NO FOREIGN KEYS")

print("\n" + "=" * 80)
print("PHASE 1B: TENANT_ID COLUMN VERIFICATION")
print("=" * 80)

for table in critical_tables:
    cur.execute("""
        SELECT column_name, is_nullable, data_type
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = 'tenant_id'
    """, (table,))

    result = cur.fetchone()
    if result:
        print(f"{table}: ✅ tenant_id ({result[2]}, nullable={result[1]})")
    else:
        print(f"{table}: ❌ NO tenant_id column")

print("\n" + "=" * 80)
print("PHASE 1C: DATA SAMPLE FOR TENANT 0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3")
print("=" * 80)

tenant_id = "0b2099ec-9ad7-4766-bff8-9e28d4a8e7d3"

# Check each table has data
for table in critical_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = %s", (tenant_id,))
    count = cur.fetchone()[0]
    print(f"{table}: {count} rows")

# Check relationships
print("\n" + "=" * 80)
print("PHASE 1D: RELATIONSHIP INTEGRITY CHECK")
print("=" * 80)

# Check if recipes reference valid menu_items and ingredients
cur.execute("""
    SELECT
        COUNT(*) as total_recipes,
        COUNT(DISTINCT r.menu_item_id) as unique_menu_items,
        COUNT(DISTINCT r.ingredient_id) as unique_ingredients
    FROM recipes r
    WHERE r.tenant_id = %s
""", (tenant_id,))
print(f"Recipes: {cur.fetchone()}")

# Check if all recipe menu_items exist
cur.execute("""
    SELECT COUNT(*)
    FROM recipes r
    LEFT JOIN menu_items mi ON r.menu_item_id = mi.id AND r.tenant_id = mi.tenant_id
    WHERE r.tenant_id = %s AND mi.id IS NULL
""", (tenant_id,))
orphaned_menu = cur.fetchone()[0]
print(f"Orphaned recipes (menu_item not found): {orphaned_menu}")

# Check if all recipe ingredients exist
cur.execute("""
    SELECT COUNT(*)
    FROM recipes r
    LEFT JOIN ingredients i ON r.ingredient_id = i.id AND r.tenant_id = i.tenant_id
    WHERE r.tenant_id = %s AND i.id IS NULL
""", (tenant_id,))
orphaned_ing = cur.fetchone()[0]
print(f"Orphaned recipes (ingredient not found): {orphaned_ing}")

conn.close()
