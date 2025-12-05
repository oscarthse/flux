#!/usr/bin/env python3
"""
Test actual API endpoints to see what data they return
"""
import requests
import json

# First, login to get session cookie
login_response = requests.post(
    "http://localhost:8000/auth/login",
    data={
        "email": "oscarthse@gmail.com",
        "password": "password123"
    },
    allow_redirects=False
)

print("=" * 80)
print("LOGIN RESPONSE")
print("=" * 80)
print(f"Status: {login_response.status_code}")
print(f"Headers: {dict(login_response.headers)}")
print(f"Cookies: {dict(login_response.cookies)}")

# Get the session cookie
session_cookie = login_response.cookies.get('flux_session')
if not session_cookie:
    print("\n❌ NO SESSION COOKIE RECEIVED!")
    exit(1)

cookies = {'flux_session': session_cookie}

# Test dashboard
print("\n" + "=" * 80)
print("DASHBOARD ENDPOINT")
print("=" * 80)
dashboard_response = requests.get(
    "http://localhost:8000/dashboard/",
    cookies=cookies
)
print(f"Status: {dashboard_response.status_code}")
print(f"Content length: {len(dashboard_response.text)}")
# Check if it contains our menu items
if "Classic Burger" in dashboard_response.text:
    print("✅ Contains 'Classic Burger'")
else:
    print("❌ Does NOT contain 'Classic Burger'")

if "BBQ Wings" in dashboard_response.text:
    print("✅ Contains 'BBQ Wings'")
else:
    print("❌ Does NOT contain 'BBQ Wings'")

# Check for metrics
if "Projected Sales" in dashboard_response.text:
    print("✅ Contains 'Projected Sales'")
else:
    print("❌ Does NOT contain 'Projected Sales'")

# Test forecasts endpoint
print("\n" + "=" * 80)
print("FORECASTS ENDPOINT")
print("=" * 80)
forecasts_response = requests.get(
    "http://localhost:8000/analytics/forecasts",
    cookies=cookies
)
print(f"Status: {forecasts_response.status_code}")
if "Classic Burger" in forecasts_response.text:
    print("✅ Contains 'Classic Burger'")
else:
    print("❌ Does NOT contain 'Classic Burger'")

# Test inventory endpoint
print("\n" + "=" * 80)
print("INVENTORY ENDPOINT")
print("=" * 80)
inventory_response = requests.get(
    "http://localhost:8000/inventory/",
    cookies=cookies
)
print(f"Status: {inventory_response.status_code}")
if "Burger Bun" in inventory_response.text:
    print("✅ Contains 'Burger Bun'")
else:
    print("❌ Does NOT contain 'Burger Bun'")

if "Chicken Wings" in inventory_response.text:
    print("✅ Contains 'Chicken Wings'")
else:
    print("❌ Does NOT contain 'Chicken Wings'")

# Save dashboard HTML for inspection
with open('/tmp/dashboard_output.html', 'w') as f:
    f.write(dashboard_response.text)
print(f"\n📄 Dashboard HTML saved to /tmp/dashboard_output.html")

# Check what's in the first 2000 chars
print("\n" + "=" * 80)
print("DASHBOARD PREVIEW (first 2000 chars)")
print("=" * 80)
print(dashboard_response.text[:2000])
