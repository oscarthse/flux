"""
Comprehensive Seeding Script for Flux Economic Chain.

This script establishes the FULL economic chain:
Menu Items (with prices) → Recipes → Ingredients (with costs) → Forecasts

The goal: Force the Inventory Engine to show correct burn rates by linking everything together.
"""
import sys
import os
import logging
from datetime import date, timedelta
import uuid

# Add project root to path
sys.path.append(os.getcwd())

from services.api.database import db_service
from services.api.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_economic_chain():
    """Seed the complete economic chain for testing."""
    tenant_id = settings.DEFAULT_TENANT_ID
    print(f"\n{'='*60}")
    print(f"🌱 SEEDING ECONOMIC CHAIN FOR TENANT: {tenant_id}")
    print(f"{'='*60}\n")

    with db_service.get_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # ==================================================================
            # STEP 0: CLEAN SLATE (for testing)
            # ==================================================================
            print("🧹 Cleaning existing data...")
            # Delete in proper order to respect foreign key constraints
            cur.execute("DELETE FROM forecasts WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM inventory_batches WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM inventory_log WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM staff_schedule WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM lost_sales WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM recipes WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM po_line_items WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM purchase_orders WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM order_line_items WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM sales_orders WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM menu_items WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM ingredients WHERE tenant_id = %s", (tenant_id,))
            print("   ✅ Cleared existing data\n")

            # ==================================================================
            # STEP 1: CREATE MENU ITEMS (with realistic prices)
            # ==================================================================
            print("📋 Creating Menu Items...")
            menu_items = {
                "Seafood Paella": {"price": 28.00, "category": "Mains"},
                "Veggie Paella": {"price": 22.00, "category": "Mains"},
                "Gourmet Burger": {"price": 18.00, "category": "Mains"},
                "Caesar Salad": {"price": 14.00, "category": "Starters"},
                "House Red Wine": {"price": 8.00, "category": "Beverages"},
            }

            menu_item_ids = {}
            for name, details in menu_items.items():
                item_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO menu_items (id, tenant_id, name, category, price, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """, (item_id, tenant_id, name, details["category"], details["price"]))
                menu_item_ids[name] = item_id
                print(f"   ✅ {name} - ${details['price']:.2f}")

            print()

            # ==================================================================
            # STEP 2: CREATE INGREDIENTS (with costs and operational params)
            # ==================================================================
            print("🥕 Creating Ingredients...")
            ingredients = {
                "Bomba Rice": {"cost": 2.50, "unit": "kg", "par": 50.0, "reorder": 20.0, "lead_time": 2},
                "Mixed Seafood": {"cost": 12.00, "unit": "kg", "par": 30.0, "reorder": 10.0, "lead_time": 1},
                "Ground Beef": {"cost": 8.00, "unit": "kg", "par": 40.0, "reorder": 15.0, "lead_time": 2},
                "Lettuce": {"cost": 1.50, "unit": "kg", "par": 20.0, "reorder": 8.0, "lead_time": 1},
                "Tomatoes": {"cost": 2.00, "unit": "kg", "par": 25.0, "reorder": 10.0, "lead_time": 1},
                "Saffron": {"cost": 45.00, "unit": "kg", "par": 1.0, "reorder": 0.2, "lead_time": 5},
                "Bell Peppers": {"cost": 3.00, "unit": "kg", "par": 15.0, "reorder": 5.0, "lead_time": 1},
                "Olive Oil": {"cost": 15.00, "unit": "L", "par": 10.0, "reorder": 3.0, "lead_time": 3},
                "Burger Buns": {"cost": 0.50, "unit": "unit", "par": 100.0, "reorder": 30.0, "lead_time": 1},
                "Red Wine (Bulk)": {"cost": 4.00, "unit": "L", "par": 50.0, "reorder": 20.0, "lead_time": 7},
            }

            ingredient_ids = {}
            for name, details in ingredients.items():
                ing_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO ingredients (id, tenant_id, name, cost_per_unit, unit,
                                            par_level, reorder_threshold, lead_time_days, shelf_life_days)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 30)
                """, (ing_id, tenant_id, name, details["cost"], details["unit"],
                      details["par"], details["reorder"], details["lead_time"]))
                ingredient_ids[name] = ing_id
                print(f"   ✅ {name} - ${details['cost']:.2f}/{details['unit']}")

            print()

            # ==================================================================
            # STEP 3: CREATE RECIPES (THE MISSING LINK!)
            # ==================================================================
            print("🔗 Creating Recipe Links...")
            recipes = [
                # Seafood Paella: 0.3kg Rice, 0.2kg Seafood, 0.001kg Saffron, 0.05L Olive Oil
                ("Seafood Paella", "Bomba Rice", 0.3),
                ("Seafood Paella", "Mixed Seafood", 0.2),
                ("Seafood Paella", "Saffron", 0.001),
                ("Seafood Paella", "Olive Oil", 0.05),
                ("Seafood Paella", "Tomatoes", 0.1),

                # Veggie Paella: 0.3kg Rice, 0.15kg Bell Peppers, 0.1kg Tomatoes
                ("Veggie Paella", "Bomba Rice", 0.3),
                ("Veggie Paella", "Bell Peppers", 0.15),
                ("Veggie Paella", "Tomatoes", 0.1),
                ("Veggie Paella", "Olive Oil", 0.05),

                # Gourmet Burger: 0.2kg Beef, 1 Bun, 0.05kg Lettuce, 0.05kg Tomatoes
                ("Gourmet Burger", "Ground Beef", 0.2),
                ("Gourmet Burger", "Burger Buns", 1.0),
                ("Gourmet Burger", "Lettuce", 0.05),
                ("Gourmet Burger", "Tomatoes", 0.05),

                # Caesar Salad: 0.2kg Lettuce, 0.05kg Tomatoes
                ("Caesar Salad", "Lettuce", 0.2),
                ("Caesar Salad", "Tomatoes", 0.05),

                # House Red Wine: 0.175L Wine (standard glass)
                ("House Red Wine", "Red Wine (Bulk)", 0.175),
            ]

            for menu_name, ing_name, qty in recipes:
                cur.execute("""
                    INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
                    VALUES (%s, %s, %s, %s)
                """, (tenant_id, menu_item_ids[menu_name], ingredient_ids[ing_name], qty))
                print(f"   ✅ {menu_name} requires {qty} of {ing_name}")

            print()

            # ==================================================================
            # STEP 4: SET INTENTIONAL STOCK LEVELS (Critical/Healthy scenarios)
            # ==================================================================
            print("📦 Setting Stock Levels (Intentional Scenarios)...")
            stock_scenarios = {
                "Bomba Rice": 0.0,        # CRITICAL: 0kg stock, but high demand
                "Mixed Seafood": 5.0,     # LOW: 5kg stock, moderate demand
                "Ground Beef": 100.0,     # HEALTHY: Plenty of stock
                "Lettuce": 3.0,           # LOW: Will run out soon
                "Tomatoes": 10.0,         # MODERATE
                "Saffron": 0.5,           # HEALTHY (low usage)
                "Bell Peppers": 20.0,     # HEALTHY
                "Olive Oil": 8.0,         # MODERATE
                "Burger Buns": 50.0,      # MODERATE
                "Red Wine (Bulk)": 100.0, # HEALTHY
            }

            for ing_name, stock in stock_scenarios.items():
                if stock > 0:
                    batch_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity, cost_per_unit)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (batch_id, tenant_id, ingredient_ids[ing_name], stock, stock, ingredients[ing_name]["cost"]))
                    print(f"   ✅ {ing_name}: {stock} {ingredients[ing_name]['unit']}")
                else:
                    print(f"   🚨 {ing_name}: 0 {ingredients[ing_name]['unit']} (CRITICAL)")

            print()

            # ==================================================================
            # STEP 5: CREATE FORECASTS (Next 14 Days)
            # ==================================================================
            print("🔮 Creating Forecasts (Next 14 Days)...")
            forecast_demands = {
                "Seafood Paella": 20,  # 20/day → 6kg Rice/day (20 × 0.3)
                "Veggie Paella": 10,   # 10/day → 3kg Rice/day (10 × 0.3)
                "Gourmet Burger": 15,  # 15/day → 3kg Beef/day (15 × 0.2)
                "Caesar Salad": 12,    # 12/day → 2.4kg Lettuce/day
                "House Red Wine": 25,  # 25/day → 4.375L Wine/day
            }

            for i in range(14):
                f_date = date.today() + timedelta(days=i)
                for menu_name, qty in forecast_demands.items():
                    cur.execute("""
                        INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity, model_version)
                        VALUES (%s, %s, %s, %s, 'seed_v1.0')
                    """, (tenant_id, menu_item_ids[menu_name], f_date, qty))

            print(f"   ✅ Created forecasts for {len(forecast_demands)} menu items × 14 days")
            print()

            # ==================================================================
            # FINAL: COMMIT AND SUMMARIZE
            # ==================================================================
            conn.commit()

            print(f"\n{'='*60}")
            print("✅ ECONOMIC CHAIN SEEDED SUCCESSFULLY!")
            print(f"{'='*60}\n")

            print("📊 EXPECTED BURN RATES (if logic is correct):")
            print(f"   • Bomba Rice: {20*0.3 + 10*0.3:.1f} kg/day (30 paellas)")
            print(f"   • Mixed Seafood: {20*0.2:.1f} kg/day")
            print(f"   • Ground Beef: {15*0.2:.1f} kg/day")
            print(f"   • Lettuce: {12*0.2 + 15*0.05:.1f} kg/day")
            print(f"   • Red Wine (Bulk): {25*0.175:.2f} L/day")
            print()

            print("🚨 EXPECTED CRITICAL STATUSES:")
            print("   • Bomba Rice: 0 stock + 9.0 kg/day burn → CRITICAL (0 days)")
            print("   • Lettuce: 3 kg / 3.15 kg/day → CRITICAL (~1 day)")
            print()

            print("✅ EXPECTED HEALTHY:")
            print("   • Ground Beef: 100 kg / 3.0 kg/day → HEALTHY (33 days)")
            print("   • Red Wine: 100 L / 4.38 L/day → HEALTHY (22 days)")
            print()

            print("🎯 SUCCESS CRITERIA:")
            print("   If you see '0 Burn Rate' for Rice, THE CODE IS WRONG!")
            print("   Rice MUST show 9.0 kg/day because forecasts exist + recipes exist.")
            print()


if __name__ == "__main__":
    seed_economic_chain()
