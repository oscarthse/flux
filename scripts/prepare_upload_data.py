import sys
import os
import csv
from datetime import datetime

# Add src to path to import simulator modules
sys.path.append(os.path.join(os.getcwd(), "src"))

from restaurant_simulator.menu import MENU_DB, INGREDIENTS_DB, MenuItem

OUTPUT_DIR = "upload_ready_data"
SIM_OUTPUT_DIR = "output_data"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def export_ingredients():
    print("Exporting Ingredients...")
    with open(f"{OUTPUT_DIR}/ingredients.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "category", "cost_per_unit", "unit", "par_level", "reorder_threshold", "lead_time_days", "shelf_life_days"])

        for ing in INGREDIENTS_DB.values():
            # Infer category
            cat = "Food"
            if ing.name in ["Red Wine", "Mineral Water", "Milk"]:
                cat = "Beverage"
            elif ing.name in ["Sugar", "Saffron", "Olive Oil"]:
                cat = "Pantry"

            writer.writerow([
                ing.name, cat, ing.cost_per_unit, ing.unit,
                ing.par_level, ing.reorder_threshold, ing.lead_time_days, ing.shelf_life_days
            ])

def export_menu():
    print("Exporting Menu...")
    with open(f"{OUTPUT_DIR}/menu_items.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "category", "price"])

        for item in MENU_DB:
            writer.writerow([item.name, item.category, item.price])

def export_recipes():
    print("Exporting Recipes...")
    with open(f"{OUTPUT_DIR}/recipes.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["menu_item_name", "ingredient_name", "quantity"])

        for item in MENU_DB:
            for recipe_item in item.recipe:
                ing_name = INGREDIENTS_DB[recipe_item.ingredient_id].name
                writer.writerow([item.name, ing_name, recipe_item.quantity])

def transform_sales():
    print("Transforming Simulation Sales Data...")

    # Load Orders
    orders = {}
    with open(f"{SIM_OUTPUT_DIR}/orders.csv", 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            orders[row['order_id']] = row['timestamp']

    # Load Items and Join
    sales_rows = []

    # Create map for ID -> Name
    menu_map = {str(item.id): item.name for item in MENU_DB}

    with open(f"{SIM_OUTPUT_DIR}/order_items.csv", 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = row['order_id']
            mi_id = row['menu_item_id']
            qty = row['quantity']

            timestamp = orders.get(order_id)
            name = menu_map.get(mi_id)

            if timestamp and name:
                sales_rows.append([timestamp, name, qty])

    with open(f"{OUTPUT_DIR}/sales_orders.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "menu_item_name", "quantity"])
        writer.writerows(sales_rows)

if __name__ == "__main__":
    export_ingredients()
    export_menu()
    export_recipes()
    transform_sales()
    print(f"DONE. Files ready in {OUTPUT_DIR}/")
