"""
Base forecasting engine and model interface.

Provides abstract base classes and main orchestration for multi-model forecasting.
"""
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """
    Forecast output with uncertainty and explainability.

    Required by downstream Newsvendor model for stochastic optimization.
    """
    date: date
    qty: float              # Point estimate (yhat)
    sigma: float            # Standard deviation for Newsvendor
    trend_impact: float     # Contribution from trend component
    day_impact: float       # Contribution from weekly seasonality
    explanation: str        # Plain English summary

    def to_tuple(self) -> Tuple[date, float]:
        """Backward compatible tuple output."""
        return (self.date, self.qty)


class ForecastModel(ABC):
    """
    Abstract base class for forecasting models.

    All forecasting models must implement fit() and predict() methods.

    Example:
        >>> class MyModel(ForecastModel):
        ...     def fit(self, sales_data):
        ...         self.avg = sum(qty for _, _, qty in sales_data) / len(sales_data)
        ...
        ...     def predict(self, menu_item_id, days):
        ...         return [(date.today() + timedelta(days=i), self.avg) for i in range(days)]
    """

    def __init__(self, tenant_id: str, conn):
        """
        Initialize model.

        Args:
            tenant_id: Tenant identifier for RLS
            conn: Database connection
        """
        self.tenant_id = tenant_id
        self.conn = conn

    @abstractmethod
    def fit(self, sales_data: List[Tuple]) -> None:
        """
        Train model on historical sales data.

        Args:
            sales_data: List of (menu_item_id, date, quantity) tuples
        """
        pass

    @abstractmethod
    def predict(self, menu_item_id: str, forecast_days: int) -> List[Tuple[date, float]]:
        """
        Generate predictions for a specific menu item.

        Args:
            menu_item_id: Menu item to forecast
            forecast_days: Number of days to predict ahead

        Returns:
            List of (forecast_date, predicted_quantity) tuples
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name for logging and comparison."""
        pass


class ForecastingEngine:
    """
    Main forecasting engine with pluggable model support.

    Handles data extraction, model selection, and forecast persistence.

    Usage:
        >>> from services.worker.engines.forecasting import ForecastingEngine
        >>> engine = ForecastingEngine(tenant_id, conn, model_name='prophet')
        >>> count = engine.generate_forecasts(forecast_days=30)
        >>> print(f"Generated {count} forecasts")
    """

    MODELS: Dict[str, type] = {}  # Populated by __init__.py

    def __init__(self, tenant_id: str, conn, model_name: str = 'moving_average'):
        """
        Initialize forecasting engine.

        Args:
            tenant_id: Tenant to generate forecasts for
            conn: Database connection
            model_name: Model to use ('moving_average' or 'prophet')

        Raises:
            ValueError: If model_name is not registered
        """
        self.tenant_id = tenant_id
        self.conn = conn
        self.model_name = model_name

        if model_name not in self.MODELS:
            available = ', '.join(self.MODELS.keys())
            raise ValueError(f"Unknown model: {model_name}. Available: {available}")

    def generate_forecasts(self, forecast_days: int = 30) -> int:
        """
        Generate forecasts using selected model.

        Process:
        1. Extract historical sales data
        2. Initialize and train model
        3. Generate predictions per menu item
        4. Save forecasts to database

        Args:
            forecast_days: Number of days to forecast ahead (default 30)

        Returns:
            Number of forecast records created
        """
        logger.info(f"[Forecasting] Starting for tenant {self.tenant_id} using {self.model_name}")

        # 1. Extract sales data
        sales_data = self._extract_sales_data()
        if not sales_data:
            logger.warning(f"[Forecasting] No sales data found for tenant {self.tenant_id}")
            return 0

        logger.info(f"[Forecasting] Extracted {len(sales_data)} historical sales records")

        # 2. Initialize model
        model_class = self.MODELS[self.model_name]
        model = model_class(self.tenant_id, self.conn)

        # 3. Train model
        logger.info(f"[Forecasting] Training {model.name} model")
        model.fit(sales_data)

        # 4. Generate forecasts per menu item
        menu_items = self._get_menu_items()
        logger.info(f"[Forecasting] Generating forecasts for {len(menu_items)} menu items")

        forecasts = []
        for menu_item_id in menu_items:
            item_forecasts = model.predict(menu_item_id, forecast_days)
            forecasts.extend([
                (menu_item_id, forecast_date, qty)
                for forecast_date, qty in item_forecasts
            ])

        # 5. Save to database
        count = self._save_forecasts(forecasts)
        logger.info(f"[Forecasting] Successfully generated {count} forecasts")

        return count

    def _extract_sales_data(self) -> List[Tuple]:
        """
        Extract historical sales aggregated by menu item and date.

        Returns:
            List of (menu_item_id, order_date, total_quantity) tuples
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    oli.menu_item_id,
                    DATE(so.timestamp) as order_date,
                    SUM(oli.quantity) as total_quantity
                FROM sales_orders so
                JOIN order_line_items oli ON so.id = oli.order_id
                WHERE so.tenant_id = %s
                GROUP BY oli.menu_item_id, DATE(so.timestamp)
                ORDER BY oli.menu_item_id, order_date
            """, (self.tenant_id,))

            return cur.fetchall()

    def _get_menu_items(self) -> List[str]:
        """
        Get list of all menu item IDs for tenant.

        Returns:
            List of menu item UUIDs
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT id FROM menu_items
                WHERE tenant_id = %s
            """, (self.tenant_id,))

            return [row[0] for row in cur.fetchall()]

    def _save_forecasts(self, forecasts: List[Tuple]) -> int:
        """
        Save forecasts to database, replacing existing ones.

        Args:
            forecasts: List of (menu_item_id, forecast_date, predicted_quantity) tuples

        Returns:
            Number of records inserted
        """
        with self.conn.cursor() as cur:
            # Clear existing forecasts for tenant
            logger.debug(f"[Forecasting] Clearing existing forecasts for tenant {self.tenant_id}")
            cur.execute("DELETE FROM forecasts WHERE tenant_id = %s", (self.tenant_id,))

            # Insert new forecasts
            count = 0
            for menu_item_id, forecast_date, qty in forecasts:
                cur.execute("""
                    INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                    VALUES (%s, %s, %s, %s)
                """, (self.tenant_id, menu_item_id, forecast_date, float(qty)))  # Convert NumPy types to Python float
                count += 1

            self.conn.commit()

        return count
