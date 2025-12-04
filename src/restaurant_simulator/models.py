from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional
from enum import Enum

class Archetype(Enum):
    TAPAS_BAR = "Tapas Bar"
    FINE_DINING = "Fine Dining"
    CASUAL_DINING = "Casual Dining"

@dataclass
class RestaurantConfig:
    archetype: Archetype
    base_turn_time_minutes: int
    seat_capacity: int
    table_mix: Dict[int, int] # {2: 10, 4: 5} means 10 tables of 2, 5 tables of 4
    menu_complexity: float # Multiplier for kitchen load
    price_point: float # Multiplier for base prices
    burstiness_parameter: float # Negative Binomial 'r' parameter

@dataclass
class Batch:
    id: str
    ingredient_id: int
    quantity: float
    received_date: date
    expiration_date: date
    cost_per_unit: float

@dataclass
class TableState:
    id: int
    seats: int
    is_occupied: bool
    release_time: Optional[datetime] = None

@dataclass
class Shift:
    name: str # "Lunch", "Dinner"
    start_hour: int
    end_hour: int
    role_counts: Dict[str, int] # {"Chef": 2, "Server": 3}
