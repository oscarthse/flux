import sys
import os
import psycopg2
from passlib.context import CryptContext

# Add project root to path
sys.path.append(os.getcwd())

from services.api import security

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

def debug_login():
    print("--- Login Debugger ---")

    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # 1. List all users
        print("\n[1] Listing Users (Raw DB):")
        cur.execute("SELECT id, email, password_hash, tenant_id FROM users")
        users = cur.fetchall()

        if not users:
            print("❌ No users found in database!")
            return

        # 2. Test App Logic (Stored Procedure)
        target_email = "oscarthse@gmail.com"
        print(f"\n[2] Testing App Logic for {target_email}:")

        cur.callproc('get_user_by_email', (target_email,))
        user = cur.fetchone()

        if user:
            print(f"  ✅ Stored Procedure returned user: {user[0]}")
            # user = (id, tenant_id, password_hash)

            # 3. Reset Password to 'password123'
            print("\n[3] Resetting Password to 'password123'...")
            new_hash = security.get_password_hash("password123")

            # Update directly
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (new_hash, target_email)
            )
            conn.commit()
            print("  ✅ Password reset committed.")

        else:
            print("  ❌ Stored Procedure returned None!")

        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_login()
