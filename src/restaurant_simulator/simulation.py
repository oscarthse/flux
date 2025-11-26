from datetime import date, timedelta
from .config import SIMULATION_START_DATE, SIMULATION_DAYS, OPERATING_HOURS
from .external_factors import ExternalFactors
from .demand import DemandSimulator
from .inventory import InventoryManager
from .staff import StaffManager
from .output import OutputManager
from .forecast import ForecastSimulator
from .menu import MENU_DB

def run_simulation(days: int = SIMULATION_DAYS):
    print(f"Starting simulation for {days} days...")

    # Initialize Modules
    factors_module = ExternalFactors()
    demand_module = DemandSimulator()
    inventory_module = InventoryManager()
    staff_module = StaffManager()
    output_module = OutputManager()
    forecast_module = ForecastSimulator()

    start_date = date.fromisoformat(SIMULATION_START_DATE)

    # Pre-calculate menu map
    menu_map = {m.id: m for m in MENU_DB}

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        print(f"Simulating {current_date}...")

        # 1. External Factors
        factors = factors_module.get_factors(current_date)

        # 2. Receive Deliveries (Morning)
        received_stock = inventory_module.receive_orders(current_date)

        # 3. Record Opening Stock (Explicitly)
        inventory_module.record_opening_stock()

        # 4. Forecast & Schedule Staff (Before Service)
        predicted_demand = forecast_module.predict_demand(current_date, factors)
        staff_schedule = staff_module.schedule_staff(current_date, predicted_demand)

        # 5. Hourly Service Loop
        daily_orders = []
        daily_lost_sales = []
        daily_used_stock = {} # Accumulate usage for logging

        for hour in OPERATING_HOURS:
            # Generate Arrivals
            arrivals = demand_module.generate_arrivals_for_hour(current_date, hour, factors)

            for arrival_ts in arrivals:
                # Create Intent (Order)
                order_intent = demand_module.create_order_for_arrival(arrival_ts)

                # Partial Fulfillment Logic
                fulfilled_items = []

                for item in order_intent.items:
                    menu_item = menu_map.get(item.menu_item_id)
                    if inventory_module.can_fulfill(menu_item, item.quantity):
                        # Fulfill this specific item
                        inventory_module.deduct_item(menu_item, item.quantity)
                        fulfilled_items.append(item)

                        # Track usage for logging
                        for recipe_item in menu_item.recipe:
                            ing_id = recipe_item.ingredient_id
                            qty = recipe_item.quantity * item.quantity
                            daily_used_stock[ing_id] = daily_used_stock.get(ing_id, 0) + qty
                    else:
                        # Log Partial Lost Sale (Specific Item)
                        lost_revenue = item.quantity * item.price_at_order
                        daily_lost_sales.append({
                            "timestamp": arrival_ts.isoformat(),
                            "party_size": order_intent.party_size,
                            "reason": f"Stockout: {menu_item.name}",
                            "potential_revenue": round(lost_revenue, 2)
                        })

                # Only record the order if at least one item was fulfilled
                if fulfilled_items:
                    order_intent.items = fulfilled_items
                    order_intent.total_amount = round(sum(i.quantity * i.price_at_order for i in fulfilled_items), 2)
                    daily_orders.append(order_intent)

        # 6. End of Day: Spoilage / Waste
        waste = inventory_module.apply_spoilage()

        # 7. Reordering
        new_orders = inventory_module.check_reorder(current_date)

        # 8. Logging
        output_module.save_orders(daily_orders)
        output_module.save_staff_schedule(staff_schedule)
        output_module.save_lost_sales(daily_lost_sales)

        # Log Inventory State
        snapshot = inventory_module.get_stock_snapshot()
        opening_snapshot = inventory_module.get_opening_stock()

        inventory_logs = []
        for ing_id, closing_qty in snapshot.items():
            inventory_logs.append({
                "date": current_date.isoformat(),
                "ingredient_id": ing_id,
                "opening_stock": round(opening_snapshot.get(ing_id, 0), 2),
                "used_qty": round(daily_used_stock.get(ing_id, 0), 2),
                "restock_qty": round(received_stock.get(ing_id, 0), 2),
                "waste_qty": round(waste.get(ing_id, 0), 2),
                "closing_stock": round(closing_qty, 2)
            })
        output_module.save_inventory_log(inventory_logs)

    print("Simulation complete. Data saved to output_data/")

if __name__ == "__main__":
    run_simulation()
