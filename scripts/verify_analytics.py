import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.getcwd()))

from src.flux_api.dependencies import get_db_connection
from src.flux_api.routers.analytics import get_daily_sales, get_inventory_recommendations

def verify():
    print("Connecting to DB...")
    db_gen = get_db_connection()
    db = next(db_gen)

    print("Testing get_daily_sales...")
    sales = get_daily_sales(db)
    print(f"Sales records: {len(sales)}")
    if len(sales) > 0:
        print(f"Sample: {sales[0]}")

    print("\nTesting get_inventory_recommendations...")
    recs = get_inventory_recommendations(db)
    print(f"Recommendations: {len(recs)}")
    if len(recs) > 0:
        print(f"Sample: {recs[0]}")

    print("\nVerification Successful!")

if __name__ == "__main__":
    verify()
