"""
Create a test user for development and testing.
"""
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from services.api.database import db_service
from services.api import security, seeding
import uuid

def create_test_user():
    """Create test user: oscarthse@gmail.com / password123"""

    email = "oscarthse@gmail.com"
    password = "password123"
    full_name = "Oscar Test"
    restaurant_name = "Test Restaurant"

    try:
        # Atomic Transaction: Tenant -> User -> Seed Data
        with db_service.get_connection(use_rls=False) as conn:
            with conn.cursor() as cur:
                # 1. Create Tenant
                tenant_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO tenants (id, name) VALUES (%s, %s) RETURNING id",
                    (tenant_id, restaurant_name)
                )

                # 2. Set RLS Context
                cur.execute("SET app.current_tenant = %s", (tenant_id,))

                # 3. Create User
                user_id = str(uuid.uuid4())
                password_hash = security.get_password_hash(password)

                cur.execute(
                    """
                    INSERT INTO users (id, tenant_id, email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s, %s, 'owner')
                    """,
                    (user_id, tenant_id, email, password_hash, full_name)
                )

                # 4. Seed Initial Data
                seeding.seed_tenant_data(tenant_id, cursor=cur)

        print(f"✅ Test user created successfully!")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   User ID: {user_id}")

    except Exception as e:
        print(f"❌ Failed to create test user: {e}")
        raise

if __name__ == "__main__":
    create_test_user()
