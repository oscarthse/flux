import sys
import os

# Mimic app.py path setup
sys.path.append(os.path.abspath(os.getcwd()))

try:
    from src.flux_api.routers.analytics import get_daily_sales
    print("Import successful!")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)
