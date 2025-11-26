from typing import List, Dict
from datetime import date
from .config import WAGE_RATES, MIN_CHEFS, MIN_SERVERS, COVERS_PER_CHEF, COVERS_PER_SERVER

class StaffManager:
    def schedule_staff(self, current_date: date, forecasted_covers: int) -> List[dict]:
        # Schedule based on FORECAST, not actuals.

        # Calculate needs
        chefs_needed = max(MIN_CHEFS, int(forecasted_covers / COVERS_PER_CHEF))
        servers_needed = max(MIN_SERVERS, int(forecasted_covers / COVERS_PER_SERVER))
        dishwashers_needed = max(1, int(forecasted_covers / 80))

        schedule = []

        # Assume 8 hour shifts for simplicity or split into lunch/dinner
        # Let's do a simple daily aggregate for MVP

        # Chefs
        schedule.append({
            "date": current_date.isoformat(),
            "role": "Chef",
            "count": chefs_needed,
            "cost": chefs_needed * 8 * WAGE_RATES["Chef"]
        })

        # Servers
        schedule.append({
            "date": current_date.isoformat(),
            "role": "Server",
            "count": servers_needed,
            "cost": servers_needed * 8 * WAGE_RATES["Server"]
        })

        # Dishwashers
        schedule.append({
            "date": current_date.isoformat(),
            "role": "Dishwasher",
            "count": dishwashers_needed,
            "cost": dishwashers_needed * 8 * WAGE_RATES["Dishwasher"]
        })

        return schedule
