import sys
import os
import logging
from datetime import date, timedelta
import random

# Add project root to path
sys.path.append(os.getcwd())

from services.api.database import db_service
from services.api.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_demo_data():
    tenant_id = settings.DEFAULT_TENANT_ID
    print(f"Seeding demo data for tenant: {tenant_id}")

    with db_service.get_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # 1. Clear existing forecasts/stock to start fresh
            cur.execute("DELETE FROM forecasts WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM inventory_batches WHERE tenant_id = %s", (tenant_id,))

            # 2. Get Ingredients
            cur.execute("SELECT id, name FROM ingredients WHERE tenant_id = %s", (tenant_id,))
            ingredients = {row[1]: row[0] for row in cur.fetchall()}

            # 3. Get Menu Items
            cur.execute("SELECT id, name FROM menu_items WHERE tenant_id = %s", (tenant_id,))
            menu_items = {row[1]: row[0] for row in cur.fetchall()}

            # 4. Seed Stock (Scenario: Low Rice, High Seafood)
            import uuid

            # Bomba Rice: 2kg (Critical - assumes high usage)
            if 'Bomba Rice' in ingredients:
                cur.execute("""
                    INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity)
                    VALUES (%s, %s, %s, 2.0, 2.0)
                """, (str(uuid.uuid4()), tenant_id, ingredients['Bomba Rice']))

            # Mixed Seafood: 50kg (Healthy)
            if 'Mixed Seafood' in ingredients:
                cur.execute("""
                    INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity)
                    VALUES (%s, %s, %s, 50.0, 50.0)
                """, (str(uuid.uuid4()), tenant_id, ingredients['Mixed Seafood']))

            # 5. Seed Forecasts (Drive Demand)
            # Seafood Paella (Uses Rice & Seafood)
            # Forecast: 20 orders/day for next 14 days
            if 'Seafood Paella' in menu_items:
                for i in range(14):
                    f_date = date.today() + timedelta(days=i)
                    cur.execute("""
                        INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                        VALUES (%s, %s, %s, 20.0)
                    """, (tenant_id, menu_items['Seafood Paella'], f_date))

            # Veggie Paella (Uses Rice)
            # Forecast: 10 orders/day
            if 'Veggie Paella' in menu_items:
                for i in range(14):
                    f_date = date.today() + timedelta(days=i)
                    cur.execute("""
                        INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                        VALUES (%s, %s, %s, 10.0)
                    """, (tenant_id, menu_items['Veggie Paella'], f_date))

            conn.commit()
            print("✅ Demo Data Seeded Successfully!")
            print("- Bomba Rice: 2kg Stock (Should be Critical)")
            print("- Mixed Seafood: 50kg Stock (Should be Healthy)")
            print("- Forecasts: 20 Seafood Paellas + 10 Veggie Paellas per day")

if __name__ == "__main__":
    seed_demo_data()
