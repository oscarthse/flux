import random
from dataclasses import dataclass
from datetime import date

@dataclass
class DailyFactors:
    date: date
    weather_condition: str # 'Sunny', 'Cloudy', 'Rain'
    temperature: float
    is_holiday: bool
    event_name: str
    demand_multiplier: float

class ExternalFactors:
    def __init__(self):
        self.holidays = {
            "2025-07-24": "Local Festival", # Example
            "2025-08-15": "Assumption Day"
        }

    def get_factors(self, current_date: date) -> DailyFactors:
        # Simple synthetic weather generation
        # Summer in Barcelona: mostly sunny/hot
        r = random.random()
        if r < 0.8:
            weather = "Sunny"
            temp = random.uniform(25, 32)
            w_factor = 1.1 # Good weather boost
        elif r < 0.95:
            weather = "Cloudy"
            temp = random.uniform(22, 28)
            w_factor = 1.0
        else:
            weather = "Rain"
            temp = random.uniform(20, 25)
            w_factor = 0.8 # Rain penalty

        date_str = current_date.isoformat()
        event = self.holidays.get(date_str, None)
        is_holiday = event is not None

        e_factor = 1.2 if is_holiday else 1.0

        # Weekend boost logic could be here, but handled in base demand usually
        # Let's just return the multipliers

        total_multiplier = w_factor * e_factor

        return DailyFactors(
            date=current_date,
            weather_condition=weather,
            temperature=round(temp, 1),
            is_holiday=is_holiday,
            event_name=event,
            demand_multiplier=total_multiplier
        )
