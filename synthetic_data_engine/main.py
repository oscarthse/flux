import argparse
from datetime import date
from .config.profiles import PROFILES
from .layers.calendar import CalendarEngine
from .simulation.service_cycle import ServiceSimulator
from .simulation.kitchen import KitchenChaos
from .output.csv_writer import CSVWriter

def main():
    parser = argparse.ArgumentParser(description="FluxSim: Agent-Based Restaurant Simulator")
    parser.add_argument("--profile", type=str, required=True, choices=PROFILES.keys(), help="Restaurant profile to simulate")
    parser.add_argument("--days", type=int, default=365, help="Number of days to simulate (from today)")
    parser.add_argument("--output", type=str, default=None, help="Custom output directory")

    args = parser.parse_args()

    profile = PROFILES[args.profile]
    print(f"🚀 Starting FluxSim for profile: {profile.name}")
    print(f"📍 Location: {profile.location} | Agent Mix: {profile.agent_mix}")

    # Setup Output
    out_dir = args.output or f"synthetic_data_engine/generated/{args.profile}"
    writer = CSVWriter(out_dir)

    # 1. Initialize Engines
    # Start form Jan 1st 2025 for clean year data
    start_date = date(2025, 1, 1)
    calendar = CalendarEngine(start_date, args.days)
    simulator = ServiceSimulator(profile)

    all_orders = []
    inventory_log_entries = []
    history = []

    print(f"⏳ Simulating {args.days} days starting {start_date}...")

    # 2. Main Loop
    for day_state in calendar.simulate_year(profile):
        history.append(day_state)

        # Simulate Service
        daily_orders = simulator.run_day(day_state.date, day_state.context)

        if not daily_orders:
            continue

        all_orders.extend(daily_orders)

        # Extract just the items for Kitchen processing
        order_items = [o[1] for o in daily_orders] # o is (time, item, agent, service)

        # Simulate Kitchen Chaos (Dirty Inventory)
        daily_usage = KitchenChaos.calculate_usage(order_items)
        inventory_log_entries.append({"date": day_state.date, "usage": daily_usage})

    print("💾 Writing CSV outputs...")
    writer.write_static_catalogs()
    writer.write_sales_log(all_orders) # Writes pos_sales_log.csv AND sales.csv
    writer.write_inventory_log(inventory_log_entries)
    writer.write_external_factors(history)

    print(f"✅ Simulation Complete! Data generated in {out_dir}")
    print(f"   - Total Orders: {len(all_orders)}")
    print(f"   - Days Simulated: {len(history)}")

if __name__ == "__main__":
    main()
