#!/usr/bin/env python3
"""
Phase 1 & 2 Diagnostic: Database Persistence Check
Verifies that uploaded CSV data is actually in the database.
"""
import sys
import os
import psycopg2

sys.path.append(os.getcwd())

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def diagnose_data_pipeline(tenant_id=None):
    print("=" * 80)
    print("PHASE 1 & 2: DATABASE PERSISTENCE DIAGNOSTIC")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # If no tenant_id provided, find the most recent one
    if not tenant_id:
        cur.execute("SELECT id, name FROM tenants ORDER BY created_at DESC LIMIT 1")
        result = cur.fetchone()
        if result:
            tenant_id = result[0]
            print(f"\n✓ Using most recent tenant: {result[1]} ({tenant_id})")
        else:
            print("\n✗ No tenants found in database!")
            return

    print(f"\nTarget Tenant ID: {tenant_id}")
    print("-" * 80)

    # CHECKPOINT 2A: Database Commit Check
    print("\n[CHECKPOINT 2A] DATABASE COMMIT VERIFICATION")
    print("-" * 80)

    # Check Ingredients
    cur.execute("SELECT COUNT(*), STRING_AGG(name, ', ') FROM ingredients WHERE tenant_id = %s", (tenant_id,))
    ing_count, ing_names = cur.fetchone()
    print(f"Ingredients: {ing_count} rows")
    if ing_names:
        print(f"  Names: {ing_names}")

    # Check Menu Items
    cur.execute("SELECT COUNT(*), STRING_AGG(name, ', ') FROM menu_items WHERE tenant_id = %s", (tenant_id,))
    menu_count, menu_names = cur.fetchone()
    print(f"Menu Items: {menu_count} rows")
    if menu_names:
        print(f"  Names: {menu_names}")

    # Check Recipes
    cur.execute("""
        SELECT COUNT(*),
               STRING_AGG(DISTINCT mi.name, ', ') as menu_items
        FROM recipes r
        JOIN menu_items mi ON r.menu_item_id = mi.id
        WHERE r.tenant_id = %s
    """, (tenant_id,))
    recipe_count, recipe_items = cur.fetchone()
    print(f"Recipes: {recipe_count} rows")
    if recipe_items:
        print(f"  Menu Items with recipes: {recipe_items}")

    # Check Sales Orders
    cur.execute("""
        SELECT COUNT(*),
               MIN(timestamp::date) as earliest,
               MAX(timestamp::date) as latest
        FROM sales_orders
        WHERE tenant_id = %s
    """, (tenant_id,))
    sales_count, earliest, latest = cur.fetchone()
    print(f"Sales Orders: {sales_count} rows")
    if earliest:
        print(f"  Date range: {earliest} to {latest}")

    # Check Inventory Batches
    cur.execute("""
        SELECT COUNT(*),
               SUM(remaining_quantity) as total_stock
        FROM inventory_batches
        WHERE tenant_id = %s
    """, (tenant_id,))
    inv_count, total_stock = cur.fetchone()
    print(f"Inventory Batches: {inv_count} rows")
    if total_stock:
        print(f"  Total stock: {total_stock}")

    # CHECKPOINT 3A & 3B: Calculation Source Check
    print("\n[CHECKPOINT 3A/3B] FORECASTS & CALCULATIONS")
    print("-" * 80)

    # Check Forecasts
    cur.execute("""
        SELECT COUNT(*),
               MIN(forecast_date) as earliest,
               MAX(forecast_date) as latest,
               STRING_AGG(DISTINCT mi.name, ', ') as items
        FROM forecasts f
        JOIN menu_items mi ON f.menu_item_id = mi.id
        WHERE f.tenant_id = %s
    """, (tenant_id,))
    forecast_count, f_earliest, f_latest, f_items = cur.fetchone()
    print(f"Forecasts: {forecast_count} rows")
    if f_earliest:
        print(f"  Date range: {f_earliest} to {f_latest}")
        print(f"  Items: {f_items}")

    # Sample forecast data
    if forecast_count > 0:
        cur.execute("""
            SELECT mi.name, f.forecast_date, f.predicted_quantity
            FROM forecasts f
            JOIN menu_items mi ON f.menu_item_id = mi.id
            WHERE f.tenant_id = %s
            ORDER BY f.forecast_date, mi.name
            LIMIT 10
        """, (tenant_id,))
        print("\n  Sample forecasts:")
        for name, date, qty in cur.fetchall():
            print(f"    {date} | {name}: {qty}")

    # DIAGNOSIS SUMMARY
    print("\n" + "=" * 80)
    print("DIAGNOSIS SUMMARY")
    print("=" * 80)

    issues = []

    if ing_count == 0:
        issues.append("⚠️  NO INGREDIENTS - Upload failed or data not committed")

    if menu_count == 0:
        issues.append("⚠️  NO MENU ITEMS - Upload failed or data not committed")

    if sales_count == 0:
        issues.append("⚠️  NO SALES DATA - Upload failed or data not committed")

    if recipe_count == 0:
        issues.append("⚠️  NO RECIPES - Cannot calculate ingredient demand")

    if inv_count == 0:
        issues.append("⚠️  NO INVENTORY - Stock seeding failed")

    if forecast_count == 0:
        issues.append("🔴 CRITICAL: NO FORECASTS - Background job failed or not triggered")

    if issues:
        print("\nISSUES DETECTED:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ All data present in database")
        print("   → If dashboard still empty, issue is in QUERY LOGIC (Phase 3B)")

    conn.close()

if __name__ == "__main__":
    diagnose_data_pipeline()
