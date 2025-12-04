"""
Test forecasting engine with real data.

This script tests the forecasting engine end-to-end:
1. Loads historical sales data from database
2. Generates forecasts using both models
3. Compares results
4. Validates forecasts exist
"""
import psycopg2
from services.api.config import get_settings
from services.worker.engines.forecasting import ForecastingEngine

settings = get_settings()
tenant_id = settings.DEFAULT_TENANT_ID

print("=" * 60)
print("FORECASTING ENGINE TEST")
print("=" * 60)

# Connect to database
conn = psycopg2.connect(settings.DATABASE_URL)

try:
    # Check if we have historical data
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sales_orders WHERE tenant_id = %s", (tenant_id,))
        order_count = cur.fetchone()[0]

        print(f"\n📊 Historical Data:")
        print(f"   - Sales Orders: {order_count}")

    if order_count == 0:
        print("\n⚠️  No historical data found!")
        print("   Run: make sim && make etl")
        exit(1)

    # Test Moving Average      print("\n🔮 Testing Moving Average Model...")
    print("-" * 60)

    try:
        engine_ma = ForecastingEngine(tenant_id, conn, model_name='moving_average')
        count_ma = engine_ma.generate_forecasts(forecast_days=30)
        print(f"✅ Moving Average: Generated {count_ma} forecasts")
    except Exception as e:
        print(f"❌ Moving Average Failed: {e}")
        count_ma = 0

    # Test Prophet
    print("\n🤖 Testing Prophet Model...")
    print("-" * 60)

    try:
        engine_prophet = ForecastingEngine(tenant_id, conn, model_name='prophet')
        count_prophet = engine_prophet.generate_forecasts(forecast_days=30)
        print(f"✅ Prophet: Generated {count_prophet} forecasts")
    except Exception as e:
        print(f"❌ Prophet Failed: {e}")
        count_prophet = 0

    # Verify forecasts in database
    print("\n📈 Database Verification...")
    print("-" * 60)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM forecasts WHERE tenant_id = %s", (tenant_id,))
        total_forecasts = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT menu_item_id)
            FROM forecasts
            WHERE tenant_id = %s
        """, (tenant_id,))
        items_with_forecasts = cur.fetchone()[0]

        print(f"   - Total Forecasts: {total_forecasts}")
        print(f"   - Menu Items with Forecasts: {items_with_forecasts}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if count_ma > 0 and count_prophet > 0:
        print("✅ Both models working!")
        print(f"   - Moving Average: {count_ma} forecasts")
        print(f"   - Prophet: {count_prophet} forecasts")
    elif count_ma > 0:
        print("⚠️  Only Moving Average working")
    elif count_prophet > 0:
        print("⚠️  Only Prophet working")
    else:
        print("❌ No models working!")

    print("\n🚀 Next Steps:")
    print("   1. Run optimization: curl -X POST http://localhost:8000/inventory/generate")
    print("   2. Check POs: psql flux -c 'SELECT COUNT(*) FROM purchase_orders;'")
    print("   3. View dashboard: http://localhost:8000/inventory/smart-order")

finally:
    conn.close()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
