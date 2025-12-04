from datetime import time
from .models import Archetype, RestaurantConfig

# City and Restaurant Settings
CITY = "Barcelona"
CURRENCY = "EUR"

# Simulation Parameters
SIMULATION_START_DATE = "2025-01-01"
SIMULATION_DAYS = 120

# Operating Hours (Barcelona style)
# Lunch: 13:00 - 16:00 (Last seating 15:45)
# Dinner: 20:00 - 24:00 (Last seating 23:30)
OPERATING_HOURS = [
    13, 14, 15, 16,
    20, 21, 22, 23
]

# 7-Day Demand Profile (Base Lambda per hour)
# Mon=0, Sun=6
# 7-Day Demand Profile (Base Lambda per hour)
# Mon=0, Sun=6
# Calibrated: Peak demand ~1.2x - 1.5x capacity, not 3x.
WEEKLY_DEMAND_PROFILE = {
    0: {13: 10, 14: 20, 15: 15, 16: 5, 20: 15, 21: 25, 22: 20, 23: 10}, # Mon (Slow)
    1: {13: 12, 14: 25, 15: 18, 16: 8, 20: 18, 21: 30, 22: 25, 23: 12}, # Tue
    2: {13: 12, 14: 25, 15: 18, 16: 8, 20: 18, 21: 30, 22: 25, 23: 12}, # Wed
    3: {13: 15, 14: 30, 15: 20, 16: 10, 20: 25, 21: 40, 22: 35, 23: 20}, # Thu
    4: {13: 20, 14: 35, 15: 25, 16: 15, 20: 30, 21: 40, 22: 35, 23: 20}, # Fri
    5: {13: 25, 14: 40, 15: 30, 16: 15, 20: 35, 21: 45, 22: 40, 23: 25}, # Sat
    6: {13: 25, 14: 40, 15: 30, 16: 15, 20: 20, 21: 30, 22: 25, 23: 15}, # Sun
}

# Default Configuration (Tapas Bar Archetype)
DEFAULT_CONFIG = RestaurantConfig(
    archetype=Archetype.TAPAS_BAR,
    base_turn_time_minutes=60, # Fast turnover
    seat_capacity=80,
    table_mix={
        2: 20, # 20 tables of 2 (flexible)
        4: 10  # 10 tables of 4
    },
    menu_complexity=1.0,
    price_point=1.0,
    burstiness_parameter=5.0 # Moderate burstiness (Higher r = Less bursty)
)

# Staffing Rules (Shift-based)
MIN_CHEFS = 1
MIN_SERVERS = 1
COVERS_PER_CHEF = 40
COVERS_PER_SERVER = 20

WAGE_RATES = {
    "Chef": 18.00,
    "Server": 12.00,
    "Dishwasher": 10.00
}

# Kitchen Constraints
# Tapas are small plates, faster to prep/plate than full entrees.
MAX_ITEMS_PER_HOUR_PER_CHEF = 60
