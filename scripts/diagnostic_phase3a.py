#!/usr/bin/env python3
"""
Phase 3A Deep Dive: Forecasting Engine Data Flow Trace
"""
import sys
import os
import psycopg2

sys.path.append(os.getcwd())

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def trace_forecasting_data_flow():
    print("=" * 80)
    print("PHASE 3A: FORECASTING ENGINE DATA FLOW TRACE")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get tenant
    cur.execute("SELECT id, name FROM tenants ORDER BY created_at DESC LIMIT 1")
    tenant_id, tenant_name = cur.fetchone()
    print(f"\nTenant: {tenant_name} ({tenant_id})")

    # STEP 1: What does the ForecastingEngine._extract_sales_data() query return?
    print("\n" + "-" * 80)
    print("[STEP 1] ForecastingEngine._extract_sales_data() Query Result")
    print("-" * 80)

    cur.execute("""
        SELECT
            oli.menu_item_id,
            DATE(so.timestamp) as order_date,
            SUM(oli.quantity) as total_quantity
        FROM sales_orders so
        JOIN order_line_items oli ON so.id = oli.order_id
        WHERE so.tenant_id = %s
        GROUP BY oli.menu_item_id, DATE(so.timestamp)
        ORDER BY oli.menu_item_id, order_date
    """, (tenant_id,))

    sales_data = cur.fetchall()
    print(f"Total rows returned: {len(sales_data)}")

    if sales_data:
        print("\nFirst 10 rows:")
        for i, (item_id, order_date, qty) in enumerate(sales_data[:10]):
            # Get item name
            cur.execute("SELECT name FROM menu_items WHERE id = %s", (item_id,))
            name_result = cur.fetchone()
            name = name_result[0] if name_result else "UNKNOWN"
            print(f"  {i+1}. {name} ({item_id}) | {order_date} | qty={qty}")
    else:
        print("⚠️  NO SALES DATA RETURNED BY QUERY!")

    # STEP 2: Check if menu_item_id format matches
    print("\n" + "-" * 80)
    print("[STEP 2] Menu Item ID Format Check")
    print("-" * 80)

    cur.execute("SELECT id, name FROM menu_items WHERE tenant_id = %s LIMIT 5", (tenant_id,))
    menu_items = cur.fetchall()
    print("Menu item IDs in database:")
    for item_id, name in menu_items:
        print(f"  {name}: {item_id} (type: {type(item_id).__name__})")

    # STEP 3: Check what MovingAverageForecast.predict() receives
    print("\n" + "-" * 80)
    print("[STEP 3] What menu_item_ids are passed to predict()?")
    print("-" * 80)

    cur.execute("SELECT DISTINCT id FROM menu_items WHERE tenant_id = %s", (tenant_id,))
    predict_ids = [row[0] for row in cur.fetchall()]
    print(f"IDs passed to predict(): {len(predict_ids)} items")
    for i, item_id in enumerate(predict_ids[:5]):
        print(f"  {i+1}. {item_id} (type: {type(item_id).__name__})")

    # STEP 4: Simulate the fit() method
    print("\n" + "-" * 80)
    print("[STEP 4] Simulating MovingAverageForecast.fit()")
    print("-" * 80)

    sales_by_item = {}
    for menu_item_id, order_date, quantity in sales_data:
        if menu_item_id not in sales_by_item:
            sales_by_item[menu_item_id] = []
        sales_by_item[menu_item_id].append((order_date, float(quantity)))

    print(f"sales_by_item dictionary has {len(sales_by_item)} keys")
    for item_id, sales in list(sales_by_item.items())[:3]:
        cur.execute("SELECT name FROM menu_items WHERE id = %s", (item_id,))
        name_result = cur.fetchone()
        name = name_result[0] if name_result else "UNKNOWN"
        print(f"  {name}: {len(sales)} sales records")

    # STEP 5: Test predict() lookup
    print("\n" + "-" * 80)
    print("[STEP 5] Testing predict() Lookup")
    print("-" * 80)

    test_item_id = predict_ids[0]
    cur.execute("SELECT name FROM menu_items WHERE id = %s", (test_item_id,))
    test_name = cur.fetchone()[0]

    print(f"Testing with: {test_name} ({test_item_id})")
    print(f"  ID in sales_by_item keys? {test_item_id in sales_by_item}")
    print(f"  Type of test_item_id: {type(test_item_id)}")

    if sales_by_item:
        first_key = list(sales_by_item.keys())[0]
        print(f"  Type of first key in sales_by_item: {type(first_key)}")
        print(f"  Are they equal? {test_item_id == first_key}")
        print(f"  String comparison: '{str(test_item_id)}' == '{str(first_key)}' = {str(test_item_id) == str(first_key)}")

    # ROOT CAUSE ANALYSIS
    print("\n" + "=" * 80)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 80)

    if len(sales_data) == 0:
        print("🔴 ISSUE: No sales data extracted from database")
        print("   → Check if sales_orders and order_line_items have data")
    elif len(sales_by_item) == 0:
        print("🔴 ISSUE: sales_by_item dictionary is empty after fit()")
        print("   → Bug in fit() method logic")
    elif test_item_id not in sales_by_item:
        print("🔴 ISSUE: menu_item_id type mismatch between fit() and predict()")
        print("   → fit() uses one type, predict() receives another")
        print(f"   → fit() keys are type: {type(list(sales_by_item.keys())[0])}")
        print(f"   → predict() receives type: {type(test_item_id)}")
    else:
        print("✅ Data flow appears correct")
        print("   → Issue must be elsewhere")

    conn.close()

if __name__ == "__main__":
    trace_forecasting_data_flow()
