from datetime import time

# City and Restaurant Settings
CITY = "Barcelona"
CURRENCY = "EUR"

# Simulation Parameters
SIMULATION_START_DATE = "2025-01-01"
SIMULATION_DAYS = 120

# Operating Hours (Barcelona style: late lunch, late dinner)
# 13:00 - 16:00 (Lunch), 20:00 - 24:00 (Dinner)
OPERATING_HOURS = [
    13, 14, 15, 16,  # Lunch
    20, 21, 22, 23   # Dinner
]

# Base Demand Profile (Average covers per hour)
# Mon-Thu, Fri, Sat, Sun
BASE_DEMAND = {
    "weekday": {
        13: 20, 14: 40, 15: 30, 16: 10,
        20: 30, 21: 50, 22: 45, 23: 20
    },
    "weekend": {
        13: 30, 14: 60, 15: 50, 16: 20,
        20: 40, 21: 70, 22: 65, 23: 40
    }
}

# Capacity
MAX_SEATS = 80
AVG_DINE_TIME_MINUTES = 90

# Staffing Rules
MIN_CHEFS = 1
MIN_SERVERS = 1
COVERS_PER_CHEF = 40
COVERS_PER_SERVER = 20

# Wage Rates (EUR/hr)
WAGE_RATES = {
    "Chef": 18.00,
    "Server": 12.00,
    "Dishwasher": 10.00
}
