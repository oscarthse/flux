"""
Prophet-based forecasting model (advanced).

Uses Facebook Prophet for sophisticated time series forecasting
with automatic seasonality detection and trend analysis.
"""
from datetime import date, timedelta
from typing import List, Tuple, Union
import pandas as pd
import logging

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    Prophet = None

from .base import ForecastModel, ForecastResult

logger = logging.getLogger(__name__)

# Confidence interval width for uncertainty calculation
INTERVAL_WIDTH = 0.95  # 95% CI
# Z-score for 95% CI = 1.96, so full width = 3.92 sigma
Z_SCORE_95 = 3.92


class ProphetForecast(ForecastModel):
    """
    Facebook Prophet forecasting model with uncertainty quantification.

    Handles:
    - Weekly seasonality (weekday vs weekend patterns)
    - Trend detection
    - Automatic handling of missing data
    - Uncertainty estimation (sigma) for Newsvendor model

    Requires:
    - prophet package installed
    - Sufficient historical data (recommended: 30+ days)

    Example:
        >>> model = ProphetForecast(tenant_id, conn)
        >>> model.fit(sales_data)
        >>> predictions = model.predict('menu-item-123', forecast_days=30)
    """

    def __init__(self, tenant_id: str, conn, **prophet_kwargs):
        """
        Initialize Prophet model.

        Args:
            tenant_id: Tenant identifier
            conn: Database connection
            **prophet_kwargs: Additional Prophet configuration
                yearly_seasonality: bool (default False - need >1 year)
                weekly_seasonality: bool (default True)
                daily_seasonality: bool (default False)
        """
        super().__init__(tenant_id, conn)

        if not PROPHET_AVAILABLE:
            raise ImportError(
                "Prophet not installed. Install with: uv pip install prophet"
            )

        # Default Prophet settings optimized for restaurant data
        self.prophet_kwargs = prophet_kwargs or {
            'yearly_seasonality': False,  # Need >365 days
            'weekly_seasonality': True,   # Weekend vs weekday
            'daily_seasonality': False,   # Too granular
            'interval_width': INTERVAL_WIDTH,  # For uncertainty
        }

        self.models = {}

    @property
    def name(self) -> str:
        """Model identifier."""
        return "prophet"

    def fit(self, sales_data: List[Tuple]) -> None:
        """
        Train Prophet model for each menu item.

        Args:
            sales_data: List of (menu_item_id, order_date, quantity) tuples
        """
        # Group sales by menu item
        sales_by_item = {}
        for menu_item_id, order_date, quantity in sales_data:
            if menu_item_id not in sales_by_item:
                sales_by_item[menu_item_id] = []

            sales_by_item[menu_item_id].append({
                'ds': order_date,
                'y': float(quantity)
            })

        # Train model for each item
        for menu_item_id, sales in sales_by_item.items():
            try:
                # Convert to DataFrame
                df = pd.DataFrame(sales)

                # Ensure datetime format
                df['ds'] = pd.to_datetime(df['ds'])

                # Require minimum data points
                if len(df) < 7:
                    logger.warning(
                        f"[Prophet] Insufficient data for {menu_item_id} "
                        f"({len(df)} days), skipping"
                    )
                    self.models[menu_item_id] = None
                    continue

                # Train Prophet model
                model = Prophet(**self.prophet_kwargs)

                # Suppress Prophet's verbose output
                with pd.option_context('mode.chained_assignment', None):
                    model.fit(df)

                self.models[menu_item_id] = model
                logger.debug(f"[Prophet] Trained model for {menu_item_id}")

            except Exception as e:
                logger.warning(
                    f"[Prophet] Training failed for {menu_item_id}: {e}"
                )
                self.models[menu_item_id] = None

    def predict(
        self,
        menu_item_id: str,
        forecast_days: int,
        return_rich: bool = True
    ) -> Union[List[ForecastResult], List[Tuple[date, float]]]:
        """
        Generate predictions using trained Prophet model.

        Args:
            menu_item_id: Menu item to forecast
            forecast_days: Number of days to predict
            return_rich: If True, return ForecastResult list; else tuple list

        Returns:
            List of ForecastResult (or legacy tuples for backward compat)
        """
        model = self.models.get(menu_item_id)

        # Fallback for items without trained model
        if model is None:
            logger.debug(
                f"[Prophet] No model for {menu_item_id}, returning zero forecast"
            )
            start_date = date.today()
            if return_rich:
                return [
                    ForecastResult(
                        date=start_date + timedelta(days=i),
                        qty=0.0,
                        sigma=0.1,  # Minimum sigma
                        trend_impact=0.0,
                        day_impact=0.0,
                        explanation="No historical data available"
                    )
                    for i in range(forecast_days)
                ]
            return [(start_date + timedelta(days=i), 0.0) for i in range(forecast_days)]

        try:
            # Create future dataframe
            future = model.make_future_dataframe(periods=forecast_days)

            # Generate forecast with uncertainty
            forecast = model.predict(future)

            # Get the last training date
            last_training_date = model.history['ds'].max().date()
            start_date = last_training_date + timedelta(days=1)

            predictions = []
            for i in range(forecast_days):
                forecast_date = start_date + timedelta(days=i)

                # Find matching prediction
                pred_row = forecast[forecast['ds'] == pd.Timestamp(forecast_date)]

                if not pred_row.empty:
                    row = pred_row.iloc[0]

                    # Point estimate (non-negative)
                    yhat = max(0.0, row['yhat'])

                    # Uncertainty bounds
                    yhat_lower = max(0.0, row['yhat_lower'])
                    yhat_upper = max(0.0, row['yhat_upper'])

                    # Calculate sigma from CI
                    # σ = (upper - lower) / 3.92 for 95% CI
                    sigma = (yhat_upper - yhat_lower) / Z_SCORE_95

                    # Clamp sigma to minimum of 0.1 * mean to prevent division errors
                    min_sigma = 0.1 * yhat if yhat > 0 else 0.1
                    sigma = max(sigma, min_sigma)

                    # Extract components for explainability
                    trend_impact = float(row.get('trend', 0))
                    day_impact = float(row.get('weekly', 0))

                    # Generate explanation
                    explanation = self._generate_explanation(
                        yhat, trend_impact, day_impact, forecast_date
                    )

                    if return_rich:
                        predictions.append(ForecastResult(
                            date=forecast_date,
                            qty=yhat,
                            sigma=sigma,
                            trend_impact=trend_impact,
                            day_impact=day_impact,
                            explanation=explanation
                        ))
                    else:
                        predictions.append((forecast_date, yhat))
                else:
                    # Fallback if date not found
                    if return_rich:
                        predictions.append(ForecastResult(
                            date=forecast_date,
                            qty=0.0,
                            sigma=0.1,
                            trend_impact=0.0,
                            day_impact=0.0,
                            explanation="Forecast date not found"
                        ))
                    else:
                        predictions.append((forecast_date, 0.0))

            return predictions

        except Exception as e:
            logger.error(f"[Prophet] Prediction failed for {menu_item_id}: {e}")
            start_date = date.today()
            if return_rich:
                return [
                    ForecastResult(
                        date=start_date + timedelta(days=i),
                        qty=0.0,
                        sigma=0.1,
                        trend_impact=0.0,
                        day_impact=0.0,
                        explanation=f"Prediction error: {str(e)}"
                    )
                    for i in range(forecast_days)
                ]
            return [(start_date + timedelta(days=i), 0.0) for i in range(forecast_days)]

    def _generate_explanation(
        self,
        yhat: float,
        trend: float,
        weekly: float,
        forecast_date: date
    ) -> str:
        """Generate plain English explanation of forecast."""
        day_name = forecast_date.strftime('%A')

        parts = [f"Predicted {yhat:.0f} units for {day_name}"]

        # Trend impact
        if abs(trend) > 0.5:
            trend_dir = "upward" if trend > 0 else "downward"
            parts.append(f"overall {trend_dir} trend (±{abs(trend):.0f})")

        # Day-of-week impact
        if abs(weekly) > 0.5:
            if weekly > 0:
                parts.append(f"{day_name} typically adds +{weekly:.0f}")
            else:
                parts.append(f"{day_name} typically reduces by {abs(weekly):.0f}")

        return ". ".join(parts) + "."
