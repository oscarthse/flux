"""
Prophet-based forecasting model (advanced).

Uses Facebook Prophet for sophisticated time series forecasting
with automatic seasonality detection and trend analysis.
"""
from datetime import date, timedelta
from typing import List, Tuple
import pandas as pd
import logging

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    Prophet = None

from .base import ForecastModel

logger = logging.getLogger(__name__)


class ProphetForecast(ForecastModel):
    """
    Facebook Prophet forecasting model.

    Handles:
    - Weekly seasonality (weekday vs weekend patterns)
    - Trend detection
    - Automatic handling of missing data

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

    def predict(self, menu_item_id: str, forecast_days: int) -> List[Tuple[date, float]]:
        """
        Generate predictions using trained Prophet model.

        Args:
            menu_item_id: Menu item to forecast
            forecast_days: Number of days to predict

        Returns:
            List of (forecast_date, predicted_quantity) tuples
        """
        model = self.models.get(menu_item_id)

        # Fallback for items without trained model
        if model is None:
            logger.debug(
                f"[Prophet] No model for {menu_item_id}, returning zero forecast"
            )
            start_date = date.today()
            return [(start_date + timedelta(days=i), 0.0) for i in range(forecast_days)]

        try:
            # Create future dataframe - this automatically extends from last training date
            future = model.make_future_dataframe(periods=forecast_days)

            # Generate forecast
            forecast = model.predict(future)

            # Get the last training date from the model's history
            last_training_date = model.history['ds'].max().date()
            start_date = last_training_date + timedelta(days=1)

            predictions = []
            for i in range(forecast_days):
                forecast_date = start_date + timedelta(days=i)

                # Find matching prediction in Prophet's forecast
                pred_row = forecast[forecast['ds'] == pd.Timestamp(forecast_date)]

                if not pred_row.empty:
                    # Use yhat (predicted value), ensure non-negative
                    yhat = max(0.0, pred_row['yhat'].iloc[0])
                    predictions.append((forecast_date, yhat))
                else:
                    # Fallback if date not found
                    predictions.append((forecast_date, 0.0))

            return predictions

        except Exception as e:
            logger.error(f"[Prophet] Prediction failed for {menu_item_id}: {e}")
            # Fallback to zero
            start_date = date.today()
            return [(start_date + timedelta(days=i), 0.0) for i in range(forecast_days)]
