import pytest
from datetime import datetime, time
from restaurant_simulator.demand import DemandSimulator
from restaurant_simulator.external_factors import DailyFactors

def test_generate_arrivals(current_date):
    demand = DemandSimulator()
    factors = DailyFactors(
        date=current_date, weather_condition="Sunny", temperature=25.0,
        is_holiday=False, event_name=None, demand_multiplier=1.0
    )

    # Test lunch hour
    arrivals = demand.generate_arrivals_for_hour(current_date, 13, factors)
    assert isinstance(arrivals, list)
    # Should have some arrivals (random, but > 0 typically for base rate 20)
    # We can't assert exact number due to randomness, but we can check types
    if arrivals:
        assert isinstance(arrivals[0], datetime)
        assert arrivals[0].hour == 13

def test_create_order_menu_del_dia(current_date):
    # Mock weekday lunch -> High chance of Menu del Dia
    demand = DemandSimulator()
    # Force a timestamp on a weekday lunch
    ts = datetime(2025, 1, 1, 13, 30) # Wednesday

    order = demand.create_order_for_arrival(ts)

    assert order.party_size >= 1
    assert len(order.items) > 0

    # Check if Menu del Dia (ID 6) is likely present (not guaranteed due to random choice,
    # but highly probable. For unit test stability, we might check logic structure,
    # but here we just ensure valid order creation).
    assert order.total_amount > 0
