#!/usr/bin/env python3
"""
Debug: What tenant_id is in the session cookie?
"""
import requests
from services.api import security

# Login
login_response = requests.post(
    "http://localhost:8000/auth/login",
    data={
        "email": "oscarthse@gmail.com",
        "password": "password123"
    },
    allow_redirects=False
)

session_cookie = login_response.cookies.get('flux_session')
print(f"Session cookie: {session_cookie[:50]}..." if session_cookie else "NO COOKIE")

if session_cookie:
    # Decode it
    payload = security.verify_session_cookie(session_cookie)
    print(f"\nDecoded payload: {payload}")
    print(f"Tenant ID in cookie: {payload.get('tenant_id')}")

    # Check what this tenant has
    import psycopg2
    import os
    DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    tenant_id = payload.get('tenant_id')
    cur.execute("SELECT name FROM menu_items WHERE tenant_id = %s LIMIT 5", (tenant_id,))
    items = [r[0] for r in cur.fetchall()]
    print(f"\nMenu items for this tenant: {items}")
    conn.close()
