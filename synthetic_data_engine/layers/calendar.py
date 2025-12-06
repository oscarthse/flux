from datetime import date, timedelta
from typing import Iterator, NamedTuple
from ..config.barcelona_calendar import get_event, BarcelonaEvent
from .weather import WeatherGenerator, WeatherCondition
from .external_shocks import ShockEngine, DayContext
from ..config.profiles import RestaurantProfile

class DailyState(NamedTuple):
    date: date
    weather: WeatherCondition
    event: BarcelonaEvent | None
    is_weekend: bool
    context: DayContext

class CalendarEngine:
    def __init__(self, start_date: date, days: int):
        self.start_date = start_date
        self.days = days
        self.weather_gen = WeatherGenerator()

    def simulate_year(self, profile: RestaurantProfile) -> Iterator[DailyState]:
        current_date = self.start_date
        for _ in range(self.days):
            # 1. Basic Date Info
            is_weekend = current_date.weekday() >= 5 # 5=Sat, 6=Sun

            # 2. Check if open
            if current_date.month not in profile.open_months:
                current_date += timedelta(days=1)
                continue

            # 3. Generate Layer Data
            weather = self.weather_gen.generate(current_date)
            event = get_event(current_date)

            # 4. Calculate Constraints
            ctx = ShockEngine.calculate_impact(profile, weather, event)

            # 5. Weekend Boost
            if is_weekend and profile.weekend_heavy:
                ctx.demand_multiplier *= 1.5

            yield DailyState(
                date=current_date,
                weather=weather,
                event=event,
                is_weekend=is_weekend,
                context=ctx
            )

            current_date += timedelta(days=1)
