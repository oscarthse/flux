import sys
import os
import psycopg2

# Add project root to path
sys.path.append(os.getcwd())

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def delete_user(email):
    print(f"--- Deleting User: {email} ---")

    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # 1. Get Tenant ID
        cur.execute("SELECT id, tenant_id FROM users WHERE email = %s", (email,))
        res = cur.fetchone()

        if not res:
            print(f"❌ User {email} not found.")
            return

        user_id, tenant_id = res
        print(f"Found User ID: {user_id}")
        print(f"Found Tenant ID: {tenant_id}")

        # 2. Delete Data in Dependency Order
        tables = [
            "order_line_items",
            "sales_orders",
            "recipes",
            "forecasts",
            "inventory_log",
            "staff_schedule",
            "lost_sales",
            "triage_items",
            "po_line_items",
            "purchase_orders",
            "inventory_batches",
            "menu_items",
            "ingredients",
            "users",
            "tenants"
        ]

        for table in tables:
            print(f"Cleaning {table}...")
            # Most tables have tenant_id, except tenants table itself uses id
            if table == "tenants":
                cur.execute(f"DELETE FROM {table} WHERE id = %s", (tenant_id,))
            else:
                cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
            print(f"  - Deleted {cur.rowcount} rows")

        conn.commit()
        print("\n✅ Cleanup Complete. You can now sign up again.")
        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()

if __name__ == "__main__":
    delete_user("oscarthse@gmail.com")
