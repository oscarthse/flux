import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from services.api.database import db_service
from services.api.routers.inventory import get_inventory_data, get_draft_orders

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_inventory():
    tenant_id = "test-tenant-123" # Use a dummy or try to find a real one if possible, but the code uses default from settings usually.
    # Actually the router uses settings.DEFAULT_TENANT_ID.
    from services.api.config import settings
    tenant_id = settings.DEFAULT_TENANT_ID

    print(f"Debugging for tenant: {tenant_id}")

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            print("1. Testing get_inventory_data (Unified Logic)...")
            # This calls the function that imports calculate_inventory_health
            inventory = get_inventory_data(tenant_id, conn)
            print(f"   Success! Found {len(inventory)} items.")
            for item in inventory[:3]:
                print(f"   - {item.name}: {item.health_status} (Risk: ${item.revenue_risk})")

            print("\n2. Testing get_draft_orders...")
            orders = get_draft_orders(tenant_id, conn)
            print(f"   Success! Found {len(orders)} orders.")
            for po in orders[:3]:
                print(f"   - PO {po.id}: {len(po.line_items)} lines")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_inventory()
