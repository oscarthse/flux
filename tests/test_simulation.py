import pytest
import os
from restaurant_simulator.simulation import run_simulation

def test_simulation_smoke():
    # Run for 1 day
    try:
        run_simulation(days=1)
    except Exception as e:
        pytest.fail(f"Simulation failed with error: {e}")

    # Check if output files exist
    assert os.path.exists("output_data/orders.csv")
    assert os.path.exists("output_data/inventory_log.csv")
    assert os.path.exists("output_data/lost_sales.csv")
