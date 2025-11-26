import psycopg2
import sys

DB_CONFIG = {
    "dbname": "flux",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def verify_data():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 1. Count Orders
        cur.execute("SELECT COUNT(*) FROM sales_orders;")
        count = cur.fetchone()[0]
        print(f"Total Orders: {count}")

        if count == 0:
            print("FAIL: No orders found.")
            sys.exit(1)

        # 2. Top Selling Item
        cur.execute("""
            SELECT m.name, SUM(oli.quantity) as total_qty
            FROM order_line_items oli
            JOIN menu_items m ON oli.menu_item_id = m.id
            GROUP BY m.name
            ORDER BY total_qty DESC
            LIMIT 1;
        """)
        top_item = cur.fetchone()
        print(f"Top Selling Item: {top_item[0]} ({top_item[1]} units)")

        # 3. Lost Sales Revenue
        cur.execute("SELECT SUM(potential_revenue) FROM lost_sales;")
        lost_rev = cur.fetchone()[0]
        print(f"Total Lost Revenue: €{lost_rev}")

        conn.close()
        print("Verification Successful.")

    except Exception as e:
        print(f"Verification Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_data()
