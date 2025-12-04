"""
Multi-model forecasting engine.

Provides demand forecasting with pluggable algorithms.

Available Models:
- moving_average: Simple baseline using trailing window average
- prophet: Advanced time series with seasonality detection

Usage:
    >>> from services.worker.engines.forecasting import ForecastingEngine
    >>>
    >>> # Use Prophet (advanced)
    >>> engine = ForecastingEngine(tenant_id, conn, model_name='prophet')
    >>> count = engine.generate_forecasts(forecast_days=30)
    >>>
    >>> # Use moving average (baseline)
    >>> engine = ForecastingEngine(tenant_id, conn, model_name='moving_average')
    >>> count = engine.generate_forecasts(forecast_days=30)
"""
from .base import ForecastingEngine, ForecastModel
from .moving_average import MovingAverageForecast
from .prophet_model import ProphetForecast

# Register available models
ForecastingEngine.MODELS = {
    'moving_average': MovingAverageForecast,
    'prophet': ProphetForecast,
}

__all__ = ['ForecastingEngine', 'ForecastModel']
