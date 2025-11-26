import sys
import os
import csv
from datetime import date

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from restaurant_simulator.simulation import run_simulation

def run_sanity_checks():
    print("\nRunning Sanity Checks...")
    output_dir = "output_data"

    # 1. Check files exist
    files = ["orders.csv", "order_items.csv", "inventory_log.csv", "staff_schedule.csv"]
    for f in files:
        path = os.path.join(output_dir, f)
        if not os.path.exists(path):
            print(f"FAIL: {f} not found.")
            return
        # Check not empty (header + data)
        with open(path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
            if len(rows) < 2:
                print(f"FAIL: {f} is empty or only has header.")
                return
    print("PASS: All output files generated and populated.")

    # 2. Check Logic: Sales vs Inventory
    # Pick a random day and ingredient. If used_qty > 0, ensure we had sales.
    # This is a loose check.

    # Load inventory log
    inv_log = []
    with open(os.path.join(output_dir, "inventory_log.csv"), 'r') as f:
        reader = csv.DictReader(f)
        inv_log = list(reader)

    total_usage = sum(float(row['used_qty']) for row in inv_log)
    if total_usage <= 0:
        print("FAIL: Total ingredient usage is 0. Sales did not trigger inventory deduction.")
        return
    print(f"PASS: Inventory usage recorded (Total: {total_usage:.2f} units).")

    # 3. Check Logic: Orders exist
    orders = []
    with open(os.path.join(output_dir, "orders.csv"), 'r') as f:
        reader = csv.DictReader(f)
        orders = list(reader)

    if len(orders) == 0:
        print("FAIL: No orders generated.")
        return
    print(f"PASS: {len(orders)} orders generated.")

    # 4. Check Staffing
    staff = []
    with open(os.path.join(output_dir, "staff_schedule.csv"), 'r') as f:
        reader = csv.DictReader(f)
        staff = list(reader)

    if len(staff) == 0:
        print("FAIL: No staff scheduled.")
        return
    print(f"PASS: Staff scheduled ({len(staff)} shifts).")

    print("ALL SANITY CHECKS PASSED.")

if __name__ == "__main__":
    # Run a short simulation
    run_simulation()
    run_sanity_checks()
