from typing import List, Dict
from datetime import date
from .config import WAGE_RATES, MIN_CHEFS, MIN_SERVERS, COVERS_PER_CHEF, COVERS_PER_SERVER, WEEKLY_DEMAND_PROFILE

class StaffManager:
    def schedule_staff(self, current_date: date, forecasted_covers: int) -> List[dict]:
        # Improved Shift-Based Logic: Schedule for PEAK demand

        day_of_week = current_date.weekday()
        daily_profile = WEEKLY_DEMAND_PROFILE.get(day_of_week, {})

        # 1. Lunch Peak (13:00 - 16:00)
        lunch_hours = [13, 14, 15, 16]
        max_lunch_arrivals = max([daily_profile.get(h, 0) for h in lunch_hours])
        # Avg party size ~2.5. Peak covers/hr
        peak_lunch_covers = max_lunch_arrivals * 2.5

        l_chefs = max(MIN_CHEFS, int(peak_lunch_covers / COVERS_PER_CHEF) + 1) # +1 buffer
        l_servers = max(MIN_SERVERS, int(peak_lunch_covers / COVERS_PER_SERVER) + 1)
        l_dish = max(1, int(peak_lunch_covers / 80))

        # 2. Dinner Peak (20:00 - 23:00)
        dinner_hours = [20, 21, 22, 23]
        max_dinner_arrivals = max([daily_profile.get(h, 0) for h in dinner_hours])
        peak_dinner_covers = max_dinner_arrivals * 2.5

        d_chefs = max(MIN_CHEFS, int(peak_dinner_covers / COVERS_PER_CHEF) + 1) # +1 buffer
        d_servers = max(MIN_SERVERS, int(peak_dinner_covers / COVERS_PER_SERVER) + 1)
        d_dish = max(1, int(peak_dinner_covers / 80))

        schedule = []

        # Lunch Shift (5 hours)
        schedule.extend([
            {"date": current_date.isoformat(), "role": "Chef", "count": l_chefs, "cost": l_chefs * 5 * WAGE_RATES["Chef"]},
            {"date": current_date.isoformat(), "role": "Server", "count": l_servers, "cost": l_servers * 5 * WAGE_RATES["Server"]},
            {"date": current_date.isoformat(), "role": "Dishwasher", "count": l_dish, "cost": l_dish * 5 * WAGE_RATES["Dishwasher"]}
        ])

        # Dinner Shift (5 hours)
        schedule.extend([
            {"date": current_date.isoformat(), "role": "Chef", "count": d_chefs, "cost": d_chefs * 5 * WAGE_RATES["Chef"]},
            {"date": current_date.isoformat(), "role": "Server", "count": d_servers, "cost": d_servers * 5 * WAGE_RATES["Server"]},
            {"date": current_date.isoformat(), "role": "Dishwasher", "count": d_dish, "cost": d_dish * 5 * WAGE_RATES["Dishwasher"]}
        ])
        return schedule
