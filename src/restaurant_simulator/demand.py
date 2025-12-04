import random
import numpy as np
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from .config import WEEKLY_DEMAND_PROFILE, DEFAULT_CONFIG
from .menu import MENU_DB, MenuItem, get_menu_items_by_category
from .external_factors import DailyFactors

@dataclass
class OrderItem:
    menu_item_id: int
    quantity: int
    price_at_order: float

@dataclass
class Order:
    id: str
    timestamp: datetime
    party_size: int
    items: List[OrderItem]
    total_amount: float

class DemandSimulator:
    def __init__(self):
        self.current_order_id = 1000

    def _get_base_arrival_rate(self, day_of_week: int, hour: int) -> float:
        daily_profile = WEEKLY_DEMAND_PROFILE.get(day_of_week, {})
        return daily_profile.get(hour, 0)

    def _generate_party_size(self, hour: int, is_weekend: bool) -> int:
        # Context-aware party size
        # Dinner (20+) and Weekends -> Larger groups
        is_dinner = hour >= 20

        if is_dinner or is_weekend:
            # {1: 10%, 2: 50%, 3: 20%, 4: 15%, 5+: 5%}
            r = random.random()
            if r < 0.1: return 1
            elif r < 0.6: return 2
            elif r < 0.8: return 3
            elif r < 0.95: return 4
            else: return random.randint(5, 8)
        else:
            # Lunch/Weekday: {1: 30%, 2: 50%, 3+: 20%}
            r = random.random()
            if r < 0.3: return 1
            elif r < 0.8: return 2
            else: return random.randint(3, 4)

    def generate_arrivals_for_hour(self, current_date: date, hour: int, factors: DailyFactors) -> List[datetime]:
        """Returns a list of arrival timestamps for the given hour using Negative Binomial."""
        day_of_week = current_date.weekday()
        base_rate = self._get_base_arrival_rate(day_of_week, hour)

        # Apply Multipliers
        adjusted_rate = base_rate * factors.demand_multiplier

        # Seasonality (Simple Sine Wave for MVP)
        # Peak in Summer (July/Aug), Low in Jan/Feb
        day_of_year = current_date.timetuple().tm_yday
        seasonality = 1.0 + 0.3 * np.sin(2 * np.pi * (day_of_year - 150) / 365) # Peak ~Day 240 (Aug)

        final_lambda = adjusted_rate * seasonality

        if final_lambda <= 0:
            return []

        # Negative Binomial Generation
        # r = burstiness, p = r / (r + lambda)
        r = DEFAULT_CONFIG.burstiness_parameter
        p = r / (r + final_lambda)

        num_arrivals = np.random.negative_binomial(r, p)

        arrivals = []
        for _ in range(num_arrivals):
            minute = random.randint(0, 59)
            ts = datetime.combine(current_date, time(hour, minute))
            arrivals.append(ts)

        arrivals.sort()
        return arrivals

    def create_order_for_arrival(self, timestamp: datetime, party_size: int) -> Order:
        """Generates an Order object (intent) for a customer arrival."""
        # Note: party_size is now passed in from the Simulation loop (after capacity check)
        hour = timestamp.hour
        day_of_week = timestamp.weekday()

        items = []

        # Logic: Lunch vs Dinner
        is_lunch = 13 <= hour <= 16
        is_dinner = hour >= 20
        is_weekday = day_of_week < 4

        # 1. Menu del Día (Weekday Lunch)
        if is_lunch and is_weekday:
            # High probability (e.g. 70%) of Menu del Día per person
            menu_del_dia = next((i for i in MENU_DB if i.name == "Menu del Día"), None)
            if menu_del_dia:
                num_menus = 0
                for _ in range(party_size):
                    if random.random() < 0.7:
                        num_menus += 1
                if num_menus > 0:
                    items.append(OrderItem(menu_del_dia.id, num_menus, menu_del_dia.price))
                remaining_people = party_size - num_menus
                if remaining_people > 0:
                    mains = get_menu_items_by_category("Main")
                    if mains:
                        for _ in range(remaining_people):
                            item = random.choice(mains)
                            items.append(OrderItem(item.id, 1, item.price))
            else:
                mains = get_menu_items_by_category("Main")
                for _ in range(party_size):
                    item = random.choice(mains)
                    items.append(OrderItem(item.id, 1, item.price))

        # 2. Tapas / Shared Plates (Dinner or Weekend Lunch)
        elif is_dinner or (is_lunch and not is_weekday):
            starters = get_menu_items_by_category("Starter")
            if starters:
                num_tapas = int(party_size * 1.5)
                num_tapas = max(party_size, num_tapas)
                for _ in range(num_tapas):
                    item = random.choice(starters)
                    items.append(OrderItem(item.id, 1, item.price))

            mains = get_menu_items_by_category("Main")
            if mains:
                if random.random() < 0.3 * (party_size / 2):
                    item = random.choice(mains)
                    items.append(OrderItem(item.id, 1, item.price))

            beverages = get_menu_items_by_category("Beverage")
            if beverages:
                for _ in range(party_size):
                    item = random.choice(beverages)
                    items.append(OrderItem(item.id, 1, item.price))

            desserts = get_menu_items_by_category("Dessert")
            if desserts and random.random() < 0.5:
                 for _ in range(random.randint(1, party_size)):
                    item = random.choice(desserts)
                    items.append(OrderItem(item.id, 1, item.price))

        else:
            mains = get_menu_items_by_category("Main")
            for _ in range(party_size):
                item = random.choice(mains)
                items.append(OrderItem(item.id, 1, item.price))

        total = sum(i.quantity * i.price_at_order for i in items)

        order = Order(
            id=str(self.current_order_id),
            timestamp=timestamp,
            party_size=party_size,
            items=items,
            total_amount=round(total, 2)
        )
        self.current_order_id += 1
        return order
