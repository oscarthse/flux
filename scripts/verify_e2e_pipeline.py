"""
End-to-End Pipeline Verification

Verifies the complete flow:
1. Forecasts exist (menu item level)
2. Recipe explosion works (menu → ingredients)
3. Inventory optimization creates POs (ingredient level)
"""
import psycopg2
from services.api.config import get_settings

settings = get_settings()
tenant_id = settings.DEFAULT_TENANT_ID

conn = psycopg2.connect(settings.DATABASE_URL)

print("=" * 70)
print("END-TO-END PIPELINE VERIFICATION")
print("=" * 70)

# Step 1: Verify Forecasts
print("\n📊 Step 1: Forecasts (Menu Item Level)")
print("-" * 70)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            COUNT(*) as total_forecasts,
            COUNT(DISTINCT menu_item_id) as items_forecasted
        FROM forecasts
        WHERE tenant_id = %s
    """, (tenant_id,))

    total, items = cur.fetchone()
    print(f"   ✓ Total Forecasts: {total}")
    print(f"   ✓ Menu Items Forecasted: {items}")

    if total == 0:
        print("\n   ❌ NO FORECASTS! Run: uv run python scripts/test_forecasting_engine.py")
        exit(1)

# Step 2: Verify Recipe Explosion (BOM)
print("\n🔧 Step 2: Recipe Explosion (Menu → Ingredients)")
print("-" * 70)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            mi.name as menu_item,
            f.predicted_quantity as forecast_qty,
            i.name as ingredient,
            r.quantity as recipe_qty,
            (f.predicted_quantity * r.quantity) as required_ingredient
        FROM forecasts f
        JOIN menu_items mi ON f.menu_item_id = mi.id
        JOIN recipes r ON mi.id = r.menu_item_id
        JOIN ingredients i ON r.ingredient_id = i.id
        WHERE f.tenant_id = %s
          AND f.forecast_date = CURRENT_DATE
        LIMIT 3
    """, (tenant_id,))

    results = cur.fetchall()

    if results:
        print("   ✓ Recipe Explosion Working:")
        for row in results:
            menu, forecast, ing, recipe, required = row
            print(f"      {forecast:.1f} {menu} × {recipe} = {required:.2f} {ing}")
    else:
        print("   ⚠️  No recipe data found (this might be okay)")

# Step 3: Simulate Inventory Calculation
print("\n📦 Step 3: Inventory Optimization Logic")
print("-" * 70)

with conn.cursor() as cur:
    # This mimics what inventory.py does
    cur.execute("""
        SELECT
            i.name as ingredient,
            SUM(f.predicted_quantity * r.quantity) / 7 as avg_daily_usage,
            i.lead_time_days,
            COALESCE(SUM(ib.remaining_quantity), 0) as current_stock
        FROM forecasts f
        JOIN recipes r ON f.menu_item_id = r.menu_item_id
        JOIN ingredients i ON r.ingredient_id = i.id
        LEFT JOIN inventory_batches ib ON i.id = ib.ingredient_id
        WHERE f.tenant_id = %s
          AND f.forecast_date >= CURRENT_DATE
          AND f.forecast_date < CURRENT_DATE + INTERVAL '7 days'
        GROUP BY i.id, i.name, i.lead_time_days
        LIMIT 5
    """, (tenant_id,))

    print("   Ingredient | Avg Daily Use | Lead Time | Current Stock | Should Order?")
    print("   " + "-" * 68)

    for row in cur.fetchall():
        ing, daily, lead, stock = row
        daily = float(daily or 0)
        lead = float(lead or 2)
        stock = float(stock or 0)

        safety = daily * lead * 0.5
        reorder_point = (daily * lead) + safety
        should_order = "YES" if stock < reorder_point else "NO"

        print(f"   {ing[:12]:<12} | {daily:>13.2f} | {lead:>9.0f} | {stock:>13.2f} | {should_order}")

# Step 4: Check Purchase Orders
print("\n🛒 Step 4: Purchase Orders (Final Output)")
print("-" * 70)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            COUNT(*) as total_pos,
            SUM(total_cost) as total_value
        FROM purchase_orders
        WHERE tenant_id = %s
    """, (tenant_id,))

    count, value = cur.fetchone()
    value = value or 0

    print(f"   Total POs: {count}")
    print(f"   Total Value: ${value:.2f}")

    if count == 0:
        print("\n   ⚠️  No POs yet. Generate with:")
        print("      curl -X POST http://localhost:8000/inventory/generate")
    else:
        # Show PO details
        cur.execute("""
            SELECT
                i.name as ingredient,
                pli.quantity,
                pli.unit_price,
                (pli.quantity * pli.unit_price) as line_total
            FROM purchase_orders po
            JOIN po_line_items pli ON po.id = pli.po_id
            JOIN ingredients i ON pli.ingredient_id = i.id
            WHERE po.tenant_id = %s
            ORDER BY po.created_at DESC
            LIMIT 10
        """, (tenant_id,))

        print("\n   📋 Purchase Order Line Items:")
        print("   " + "-" * 68)
        print("   Ingredient        | Quantity | Unit Price | Line Total")
        print("   " + "-" * 68)

        for row in cur.fetchall():
            ing, qty, price, total = row
            print(f"   {ing[:16]:<16} | {qty:>8.2f} | ${price:>9.2f} | ${total:>10.2f}")

# Summary
print("\n" + "=" * 70)
print("PIPELINE STATUS")
print("=" * 70)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM forecasts WHERE tenant_id = %s) as forecasts,
            (SELECT COUNT(*) FROM purchase_orders WHERE tenant_id = %s) as pos
    """, (tenant_id, tenant_id))

    forecasts, pos = cur.fetchone()

    if forecasts > 0 and pos > 0:
        print("✅ COMPLETE: Forecasts → Recipe Explosion → Purchase Orders")
        print(f"   {forecasts} forecasts generated {pos} purchase orders")
    elif forecasts > 0 and pos == 0:
        print("⚠️  PARTIAL: Forecasts exist but no POs")
        print("   Run: curl -X POST http://localhost:8000/inventory/generate")
    else:
        print("❌ INCOMPLETE: Missing forecasts")
        print("   Run: uv run python scripts/test_forecasting_engine.py")

conn.close()

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
