import os
import sys
import pandas as pd
import psycopg2
from psycopg2 import sql

# Add src to path to import menu definitions
sys.path.append(os.path.join(os.getcwd(), "src"))
from restaurant_simulator.menu import MENU_DB, INGREDIENTS_DB

DB_CONFIG = {
    "dbname": "flux",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        sys.exit(1)

def truncate_tables(conn):
    print("Truncating tables...")
    with conn.cursor() as cur:
        # Order matters due to FK constraints
        cur.execute("TRUNCATE TABLE order_line_items CASCADE;")
        cur.execute("TRUNCATE TABLE sales_orders CASCADE;")
        cur.execute("TRUNCATE TABLE inventory_log CASCADE;")
        cur.execute("TRUNCATE TABLE staff_schedule CASCADE;")
        cur.execute("TRUNCATE TABLE lost_sales CASCADE;")
        cur.execute("TRUNCATE TABLE recipes CASCADE;")
        cur.execute("TRUNCATE TABLE menu_items CASCADE;")
        cur.execute("TRUNCATE TABLE ingredients CASCADE;")
    conn.commit()

def load_master_data(conn):
    print("Loading Master Data...")
    with conn.cursor() as cur:
        # 1. Ingredients
        for ing in INGREDIENTS_DB.values():
            cur.execute("""
                INSERT INTO ingredients (id, name, cost_per_unit, unit, par_level, reorder_threshold, lead_time_days, shelf_life_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (ing.id, ing.name, ing.cost_per_unit, ing.unit, ing.par_level, ing.reorder_threshold, ing.lead_time_days, ing.shelf_life_days))

        # 2. Menu Items
        for item in MENU_DB:
            cur.execute("""
                INSERT INTO menu_items (id, name, category, price)
                VALUES (%s, %s, %s, %s)
            """, (item.id, item.name, item.category, item.price))

            # 3. Recipes
            for recipe_item in item.recipe:
                cur.execute("""
                    INSERT INTO recipes (menu_item_id, ingredient_id, quantity)
                    VALUES (%s, %s, %s)
                """, (item.id, recipe_item.ingredient_id, recipe_item.quantity))

    conn.commit()

def load_csv_data(conn):
    print("Loading CSV Data...")
    output_dir = "output_data"

    # Helper to load DF to SQL
    # Using pandas for ease, though COPY command is faster for huge data.
    # For MVP size, INSERT is fine.

    with conn.cursor() as cur:
        # 1. Sales Orders
        df_orders = pd.read_csv(os.path.join(output_dir, "orders.csv"))
        for _, row in df_orders.iterrows():
            cur.execute("""
                INSERT INTO sales_orders (id, timestamp, party_size, total_amount)
                VALUES (%s, %s, %s, %s)
            """, (str(int(row['order_id'])), row['timestamp'], int(row['party_size']), float(row['total_amount'])))

        # 2. Order Line Items
        df_items = pd.read_csv(os.path.join(output_dir, "order_items.csv"))
        for _, row in df_items.iterrows():
            cur.execute("""
                INSERT INTO order_line_items (order_id, menu_item_id, quantity, price_at_order)
                VALUES (%s, %s, %s, %s)
            """, (str(int(row['order_id'])), int(row['menu_item_id']), int(row['quantity']), float(row['price_at_order'])))

        # 3. Inventory Log
        df_inv = pd.read_csv(os.path.join(output_dir, "inventory_log.csv"))
        for _, row in df_inv.iterrows():
            cur.execute("""
                INSERT INTO inventory_log (date, ingredient_id, opening_stock, used_qty, waste_qty, closing_stock)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (row['date'], int(row['ingredient_id']), float(row['opening_stock']), float(row['used_qty']), float(row['waste_qty']), float(row['closing_stock'])))

        # 4. Staff Schedule
        df_staff = pd.read_csv(os.path.join(output_dir, "staff_schedule.csv"))
        for _, row in df_staff.iterrows():
            cur.execute("""
                INSERT INTO staff_schedule (date, role, count, cost)
                VALUES (%s, %s, %s, %s)
            """, (row['date'], row['role'], int(row['count']), float(row['cost'])))

        # 5. Lost Sales
        lost_sales_path = os.path.join(output_dir, "lost_sales.csv")
        if os.path.exists(lost_sales_path):
            df_lost = pd.read_csv(lost_sales_path)
            for _, row in df_lost.iterrows():
                cur.execute("""
                    INSERT INTO lost_sales (timestamp, party_size, reason, potential_revenue)
                    VALUES (%s, %s, %s, %s)
                """, (row['timestamp'], int(row['party_size']), row['reason'], float(row['potential_revenue'])))

    conn.commit()

def run_etl():
    conn = get_db_connection()
    truncate_tables(conn)
    load_master_data(conn)
    load_csv_data(conn)
    conn.close()
    print("ETL Complete.")

if __name__ == "__main__":
    run_etl()
