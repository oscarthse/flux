import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional
from .models import TableState, RestaurantConfig
from .config import MAX_ITEMS_PER_HOUR_PER_CHEF

class TableManager:
    def __init__(self, config: RestaurantConfig):
        self.config = config
        self.tables: List[TableState] = []
        self._init_tables()

    def _init_tables(self):
        table_id = 1
        for size, count in self.config.table_mix.items():
            for _ in range(count):
                self.tables.append(TableState(id=table_id, seats=size, is_occupied=False))
                table_id += 1

    def update_state(self, current_time: datetime):
        """Release tables whose time is up."""
        for table in self.tables:
            if table.is_occupied and table.release_time and current_time >= table.release_time:
                table.is_occupied = False
                table.release_time = None

    def try_seat(self, party_size: int, current_time: datetime) -> bool:
        """
        Attempt to seat a party. Returns True if successful.
        Uses Best Fit Bin Packing.
        """
        # 1. Find available tables that fit the party
        candidates = [t for t in self.tables if not t.is_occupied and t.seats >= party_size]

        if not candidates:
            return False

        # 2. Select best fit (smallest table that fits)
        selected_table = min(candidates, key=lambda t: t.seats)

        # 3. Determine Duration (LogNormal)
        # Mean of log-normal is exp(mu + sigma^2/2). We want Mean = base_turn_time.
        # Simple approximation: mu = ln(base_time), sigma = 0.2
        mu = np.log(self.config.base_turn_time_minutes)
        sigma = 0.2
        duration_minutes = np.random.lognormal(mu, sigma)

        # 4. Update State
        selected_table.is_occupied = True
        selected_table.release_time = current_time + timedelta(minutes=duration_minutes)

        return True

class KitchenManager:
    def __init__(self, num_chefs: int):
        self.num_chefs = num_chefs
        self.current_load_items = 0
        self.hourly_capacity = num_chefs * MAX_ITEMS_PER_HOUR_PER_CHEF

    def reset_hour(self, num_chefs: int):
        self.num_chefs = num_chefs
        self.hourly_capacity = num_chefs * MAX_ITEMS_PER_HOUR_PER_CHEF
        self.current_load_items = 0

    def check_capacity(self, num_items: int) -> bool:
        """
        Check if kitchen can handle this order within reasonable time.
        Simple logic: If load > capacity * 1.2 (20% buffer), reject or delay.
        For MVP, we reject (Balking due to wait times).
        """
        if self.current_load_items + num_items > self.hourly_capacity * 1.2:
            return False
        return True

    def add_order(self, num_items: int):
        self.current_load_items += num_items
