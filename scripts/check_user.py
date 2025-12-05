#!/usr/bin/env python3
"""
Check if user oscarthse@gmail.com exists and verify password
"""
import sys
import os
import psycopg2
from passlib.context import CryptContext

sys.path.append(os.getcwd())

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Check user
cur.execute("SELECT id, email, password_hash, tenant_id FROM users WHERE email = 'oscarthse@gmail.com'")
user = cur.fetchone()

if not user:
    print("❌ User does NOT exist!")
else:
    user_id, email, password_hash, tenant_id = user
    print(f"✅ User exists:")
    print(f"   ID: {user_id}")
    print(f"   Email: {email}")
    print(f"   Tenant ID: {tenant_id}")
    print(f"   Password hash: {password_hash[:50]}...")

    # Test password
    is_valid = pwd_context.verify("password123", password_hash)
    print(f"\n   Password 'password123' valid? {is_valid}")

    if not is_valid:
        print("\n   ⚠️  PASSWORD MISMATCH - Resetting to 'password123'")
        new_hash = pwd_context.hash("password123")
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
        conn.commit()
        print("   ✅ Password reset complete")

conn.close()
