"""
Centralized configuration management for Flux Platform.

This module provides type-safe configuration using Pydantic Settings with
automatic environment variable loading. All application configuration should
be accessed through the singleton `settings` instance.

Usage:
    >>> from services.api.config import settings
    >>>
    >>> # Access database configuration
    >>> db_url = settings.DATABASE_URL
    >>>
    >>> # Access tenant configuration
    >>> tenant_id = settings.DEFAULT_TENANT_ID
    >>>
    >>> # Override via environment variables
    >>> # Set DATABASE_URL=postgresql://... in .env file

Environment Variables:
    All settings can be overridden via environment variables with the same
    name. For example:
    - DATABASE_URL: PostgreSQL connection string
    - REDIS_URL: Redis connection string
    - DEFAULT_TENANT_ID: UUID of default tenant (prototype mode)
    - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)

Configuration File:
    Create a `.env` file in the project root to override defaults:
    ```
    DATABASE_URL=postgresql://user:pass@localhost:5432/flux
    REDIS_URL=redis://localhost:6379/0
    LOG_LEVEL=DEBUG
    ```
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    This class uses Pydantic Settings to provide type-safe configuration
    with automatic validation and environment variable loading.

    Attributes:
        DATABASE_URL: PostgreSQL connection string
        DB_POOL_SIZE: Maximum number of database connections in pool
        DB_MAX_OVERFLOW: Maximum overflow connections beyond pool size
        DEFAULT_TENANT_ID: UUID of default tenant (single-tenant prototype)
        ENABLE_RLS: Enable Row Level Security tenant isolation
        REDIS_URL: Redis connection string for caching/queues
        REDIS_CACHE_TTL: Default cache TTL in seconds
        API_HOST: API server host address
        API_PORT: API server port
        API_DEBUG: Enable debug mode
        API_RELOAD: Enable auto-reload on code changes
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        LOG_FORMAT: Log message format string
        SAFETY_STOCK_MULTIPLIER: Multiplier for safety stock calculations
        LEAD_TIME_DAYS: Default ingredient lead time in days
        REVIEW_PERIOD_DAYS: Inventory review period in days
        FORECAST_HORIZON_DAYS: Forecasting horizon in days
        CONFIDENCE_INTERVAL: Statistical confidence interval (0-1)

    Example:
        >>> settings = Settings()
        >>> print(settings.DATABASE_URL)
        postgresql://postgres:postgres@localhost:5432/flux

        >>> # Override with environment variable
        >>> os.environ['DATABASE_URL'] = 'postgresql://custom'
        >>> settings = Settings()
        >>> print(settings.DATABASE_URL)
        postgresql://custom
    """

    # Database Configuration
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/flux"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Multi-tenant Configuration (Prototype - Single Tenant)
    DEFAULT_TENANT_ID: str = "a73ba506-b078-42b3-91f6-fd168c958ee2"
    ENABLE_RLS: bool = True

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hour

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    API_RELOAD: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-prod"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # Forecasting Configuration
    FORECAST_MODEL: str = "prophet"  # Options: 'prophet', 'moving_average'
    FORECAST_DAYS: int = 30
    FORECAST_LOOKBACK: int = 28
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Inventory Optimization Config
    SAFETY_STOCK_MULTIPLIER: float = 0.5
    LEAD_TIME_DAYS: int = 3
    REVIEW_PERIOD_DAYS: int = 3

    # Forecasting Config
    FORECAST_HORIZON_DAYS: int = 7
    CONFIDENCE_INTERVAL: float = 0.95

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance (singleton pattern).

    Using lru_cache ensures we only create one Settings instance
    and reuse it across the entire application, improving performance
    and consistency.

    Returns:
        Settings: Singleton settings instance

    Example:
        >>> from services.api.config import get_settings
        >>>
        >>> settings1 = get_settings()
        >>> settings2 = get_settings()
        >>> assert settings1 is settings2  # Same instance

    Note:
        The settings are cached for the lifetime of the application.
        To reload settings, restart the application.
    """
    return Settings()


# Convenience singleton export for direct import
# Usage: from services.api.config import settings
settings = get_settings()
