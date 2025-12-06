import random
from datetime import datetime, time, timedelta, date
from typing import List, Tuple, Dict
from dataclasses import dataclass

from ..config.profiles import RestaurantProfile
from ..config.agents import AGENTS, AgentArchetype
from ..layers.external_shocks import DayContext
from .customer_agents import CustomerAgent
from ..config.catalog import MenuItem

@dataclass
class ServiceResult:
    orders: List[Tuple[datetime, MenuItem, str]] # time, item, agent_name
    total_revenue: float

class ServiceSimulator:
    def __init__(self, profile: RestaurantProfile):
        self.profile = profile

    def _get_agent_archetype(self) -> AgentArchetype:
        """Randomly selects an archetype based on the profile's mix."""
        types = list(self.profile.agent_mix.keys())
        weights = list(self.profile.agent_mix.values())
        choice = random.choices(types, weights=weights, k=1)[0]
        return AGENTS[choice]

    def run_day(self, date_obj: date, ctx: DayContext) -> List[Tuple[datetime, MenuItem, str, str]]:
        """Run both Lunch and Dinner services. Returns flat list of orders."""
        all_orders = []

        # Lunch: 13:00 - 15:30
        lunch_orders = self._simulate_service(
            date_obj, "lunch", time(13, 0), time(15, 30), ctx
        )
        all_orders.extend(lunch_orders)

        # Dinner: 20:30 - 23:30
        dinner_orders = self._simulate_service(
            date_obj, "dinner", time(20, 30), time(23, 30), ctx
        )
        all_orders.extend(dinner_orders)

        return all_orders

    def _simulate_service(self, date_obj: date, service_name: str, start_t: time, end_t: time, ctx: DayContext) -> List[Tuple[datetime, MenuItem, str, str]]:
        orders = []

        # 1. Determine Total Covers
        # Capacity * Turns * Utilization * Demand Multiplier
        # Lunch Turns: Duration / AvgTurnover
        duration_min = (datetime.combine(date.min, end_t) - datetime.combine(date.min, start_t)).seconds / 60
        avg_turnover = self.profile.avg_turnover_minutes_lunch if service_name == "lunch" else self.profile.avg_turnover_minutes_dinner

        turns = duration_min / avg_turnover
        max_covers = ctx.effective_capacity * turns

        # Realized covers = Max * Demand Factor (random noise) * External Shock
        occupancy_rate = random.uniform(0.6, 1.0) # Base variation
        actual_covers = int(max_covers * occupancy_rate * ctx.demand_multiplier)

        # 2. Spawn Agents
        for _ in range(actual_covers):
            archetype = self._get_agent_archetype()
            agent = CustomerAgent(archetype)

            # 3. Determine Arrival Time
            if service_name == "lunch":
                mean_h, sigma_m = archetype.arrival_time_dist_lunch
            else:
                mean_h, sigma_m = archetype.arrival_time_dist_dinner

            # Generate gaussian minute offest from midnight
            arrival_min_abs = int(random.normalvariate(mean_h * 60, sigma_m))

            # Clamp to service hours (rough check)
            service_start_min = start_t.hour * 60 + start_t.minute
            service_end_min = end_t.hour * 60 + end_t.minute
            arrival_min_abs = max(service_start_min, min(arrival_min_abs, service_end_min - 30))

            arrival_time = (datetime.combine(date_obj, time(0, 0)) + timedelta(minutes=arrival_min_abs))

            # 4. Generate Orders
            agent_items = agent.generate_order(service_name, ctx.price_multiplier)

            for item in agent_items:
                # Add tiny random delay for ordering after arrival
                order_time = arrival_time + timedelta(minutes=random.randint(5, 20))
                orders.append((order_time, item, archetype.name, service_name))

        # Sort by time
        orders.sort(key=lambda x: x[0])
        return orders
