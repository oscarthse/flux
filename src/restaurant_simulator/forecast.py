import random
from datetime import date
from .external_factors import DailyFactors
from .config import WEEKLY_DEMAND_PROFILE

class ForecastSimulator:
    def __init__(self, error_margin: float = 0.15):
        self.error_margin = error_margin # +/- 15% error

    def predict_demand(self, target_date: date, factors: DailyFactors) -> int:
        # Calculate "Perfect" demand first
        day_of_week = target_date.weekday()
        daily_profile = WEEKLY_DEMAND_PROFILE.get(day_of_week, {})

        base_total = sum(daily_profile.values())

        # Apply factors (Weather, Events)
        # In reality, forecast might know events but guess weather wrong.
        # For MVP, we assume we know the factors but have random noise in the model.
        predicted_total = base_total * factors.demand_multiplier

        # Apply Forecast Error (Variance)
        # A random swing representing model inaccuracy
        noise = random.uniform(1 - self.error_margin, 1 + self.error_margin)

        return int(predicted_total * noise)
