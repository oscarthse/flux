#!/usr/bin/env python3
"""
Cleanup duplicate menu items and re-run forecasting
"""
import sys
import os
import psycopg2

sys.path.append(os.getcwd())

from services.worker.engines.forecasting import ForecastingEngine

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def cleanup_and_reforecast():
    print("=" * 80)
    print("CLEANUP & REFORECAST")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get tenant
    cur.execute("SELECT id, name FROM tenants ORDER BY created_at DESC LIMIT 1")
    tenant_id, tenant_name = cur.fetchone()
    print(f"\nTenant: {tenant_name} ({tenant_id})")

    # Step 1: Find duplicates
    print("\n[STEP 1] Finding duplicate menu items...")
    cur.execute("""
        SELECT name, COUNT(*), ARRAY_AGG(id) as ids
        FROM menu_items
        WHERE tenant_id = %s
        GROUP BY name
        HAVING COUNT(*) > 1
    """, (tenant_id,))

    duplicates = cur.fetchall()
    print(f"Found {len(duplicates)} duplicate item names")

    # Step 2: For each duplicate, keep the one with sales data, delete others
    for name, count, ids_array in duplicates:
        # Parse PostgreSQL array format
        ids = [id.strip() for id in ids_array.strip('{}').split(',')]
        print(f"\n  {name}: {count} copies")

        # Find which ID has sales data
        for item_id in ids:
            cur.execute("""
                SELECT COUNT(*) FROM order_line_items
                WHERE menu_item_id = %s
            """, (item_id,))
            sales_count = cur.fetchone()[0]

            if sales_count > 0:
                print(f"    Keeping {item_id} (has {sales_count} sales)")
                keep_id = item_id
                break
        else:
            # No sales data, just keep the first one
            keep_id = ids[0]
            print(f"    Keeping {keep_id} (no sales data, arbitrary choice)")

        # Update external_id for the one we're keeping (if not already set)
        cur.execute("SELECT external_id FROM menu_items WHERE id = %s", (keep_id,))
        current_external_id = cur.fetchone()[0]

        if current_external_id != name:
            cur.execute("""
                UPDATE menu_items
                SET external_id = %s
                WHERE id = %s
            """, (name, keep_id))
            print(f"    Updated external_id to '{name}'")

        # Delete the others
        for item_id in ids:
            if item_id != keep_id:
                # First delete dependent records
                cur.execute("DELETE FROM recipes WHERE menu_item_id = %s", (item_id,))
                cur.execute("DELETE FROM order_line_items WHERE menu_item_id = %s", (item_id,))
                cur.execute("DELETE FROM forecasts WHERE menu_item_id = %s", (item_id,))
                cur.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
                print(f"    Deleted {item_id}")

    conn.commit()

    # Step 3: Re-run forecasting
    print("\n[STEP 3] Re-running forecasting engine...")
    engine = ForecastingEngine(tenant_id, conn, model_name='moving_average')
    count = engine.generate_forecasts(forecast_days=7)
    conn.commit()
    print(f"✅ Generated {count} forecasts")

    # Step 4: Verify results
    print("\n[STEP 4] Verification...")
    cur.execute("""
        SELECT mi.name, f.forecast_date, f.predicted_quantity
        FROM forecasts f
        JOIN menu_items mi ON f.menu_item_id = mi.id
        WHERE f.tenant_id = %s
        AND f.predicted_quantity > 0
        ORDER BY f.forecast_date, mi.name
        LIMIT 10
    """, (tenant_id,))

    results = cur.fetchall()
    if results:
        print("Sample non-zero forecasts:")
        for name, date, qty in results:
            print(f"  {date} | {name}: {qty}")
    else:
        print("⚠️  Still no non-zero forecasts!")

    conn.close()
    print("\n" + "=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    cleanup_and_reforecast()
