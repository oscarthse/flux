"""Unit tests for configuration module."""
import pytest
import os
from services.api.config import Settings, get_settings


@pytest.mark.unit
def test_settings_defaults():
    """Test default settings values."""
    settings = Settings()
    assert "postgresql://" in settings.DATABASE_URL
    assert settings.DB_POOL_SIZE == 10
    assert settings.LOG_LEVEL == "INFO"
    assert settings.LEAD_TIME_DAYS == 3


@pytest.mark.unit
def test_settings_from_env(monkeypatch):
    """Test settings override from environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://custom:5432/test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DB_POOL_SIZE", "25")

    # Create new settings instance
    settings = Settings()
    assert settings.DATABASE_URL == "postgresql://custom:5432/test"
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.DB_POOL_SIZE == 25


@pytest.mark.unit
def test_get_settings_singleton():
    """Test settings singleton pattern."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2, "get_settings() should return same instance"


@pytest.mark.unit
def test_settings_immutability():
    """Test that settings values are validated."""
    with pytest.raises(Exception):
        # Pydantic should validate types
        Settings(DB_POOL_SIZE="not_a_number")


@pytest.mark.unit
def test_settings_has_required_fields():
    """Test that all required config fields exist."""
    settings = Settings()

    # Database config
    assert hasattr(settings, 'DATABASE_URL')
    assert hasattr(settings, 'DB_POOL_SIZE')
    assert hasattr(settings, 'DB_MAX_OVERFLOW')

    # Tenant config
    assert hasattr(settings, 'DEFAULT_TENANT_ID')
    assert hasattr(settings, 'ENABLE_RLS')

    # Redis config
    assert hasattr(settings, 'REDIS_URL')

    # Inventory config
    assert hasattr(settings, 'SAFETY_STOCK_MULTIPLIER')
    assert hasattr(settings, 'LEAD_TIME_DAYS')
