import sys
import os
import logging
from datetime import date

# Add project root to path
sys.path.append(os.getcwd())

from services.api.database import db_service
from services.api.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_data_state():
    tenant_id = settings.DEFAULT_TENANT_ID
    print(f"Checking data for tenant: {tenant_id}")

    with db_service.get_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # 1. Check Stock
            cur.execute("""
                SELECT i.name, SUM(ib.remaining_quantity)
                FROM ingredients i
                LEFT JOIN inventory_batches ib ON i.id = ib.ingredient_id
                WHERE i.tenant_id = %s
                GROUP BY i.name
            """, (tenant_id,))
            stock = cur.fetchall()
            print("\n--- Current Stock ---")
            for name, qty in stock:
                print(f"{name}: {qty or 0.0}")

            # 2. Check Forecasts
            cur.execute("""
                SELECT m.name, f.forecast_date, f.predicted_quantity
                FROM forecasts f
                JOIN menu_items m ON f.menu_item_id = m.id
                WHERE f.tenant_id = %s AND f.forecast_date >= CURRENT_DATE
                ORDER BY f.forecast_date ASC
                LIMIT 5
            """, (tenant_id,))
            forecasts = cur.fetchall()
            print("\n--- Upcoming Forecasts ---")
            if not forecasts:
                print("NO FORECASTS FOUND (This explains the 0.0 Burn Rate)")
            for row in forecasts:
                print(f"{row[0]} ({row[1]}): {row[2]}")

if __name__ == "__main__":
    check_data_state()
