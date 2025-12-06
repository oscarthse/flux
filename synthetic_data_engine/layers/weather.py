import random
import math
from datetime import date
from dataclasses import dataclass

@dataclass
class WeatherCondition:
    temperature: float
    rain_mm: float
    is_rainy: bool

class WeatherGenerator:
    def __init__(self):
        # Base temps by month (Barcelona approx)
        self.avg_temps = {
            1: 10, 2: 11, 3: 13, 4: 15, 5: 18, 6: 22,
            7: 25, 8: 26, 9: 23, 10: 19, 11: 14, 12: 11
        }
        # Rain probability by month
        self.rain_prob = {
            1: 0.15, 2: 0.15, 3: 0.20, 4: 0.25, 5: 0.20, 6: 0.10,
            7: 0.05, 8: 0.10, 9: 0.25, 10: 0.30, 11: 0.25, 12: 0.15
        }

    def generate(self, d: date) -> WeatherCondition:
        month = d.month

        # Temp noise
        base_temp = self.avg_temps[month]
        temp_noise = random.uniform(-3, 3)
        temp = base_temp + temp_noise

        # Rain logic
        is_raining = random.random() < self.rain_prob[month]
        rain_mm = 0.0

        if is_raining:
            # Pareto distribution for rain amount (mostly light, rarely heavy)
            rain_mm = random.paretovariate(2) * 2
            temp -= 2 # Rain cools it down

        return WeatherCondition(
            temperature=round(temp, 1),
            rain_mm=round(rain_mm, 1),
            is_rainy=rain_mm > 0.5
        )
