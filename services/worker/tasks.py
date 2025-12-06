import dramatiq
from dramatiq.brokers.redis import RedisBroker
import os
import logging
from lib.flux_lib.db import get_db_connection

# Configure worker logger
logger = logging.getLogger(__name__)

# Setup Broker (Must match API)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
broker = RedisBroker(url=redis_url)
dramatiq.set_broker(broker)

@dramatiq.actor(queue_name="ingest")
def ingest_pos_data(tenant_id: str, source: str, payload: dict):
    """
    Worker task to process POS data.
    """
    logger.info("Received ingestion task", extra={"tenant_id": tenant_id, "source": source})

    # 1. DB Context
    with get_db_connection(tenant_id=tenant_id) as conn:
        from services.worker.engines.ingestion import process_ingestion
        process_ingestion(tenant_id, source, payload, conn)

    logger.info("Ingestion complete", extra={"tenant_id": tenant_id})

@dramatiq.actor(queue_name="default")
def generate_daily_forecast(tenant_id: str):
    """
    Nightly task to generate forecasts for the next 7 days.
    """
    from services.worker.engines.forecasting import generate_forecast
    from datetime import date, timedelta

    logger.info("Starting forecast generation", extra={"tenant_id": tenant_id})

    with get_db_connection(tenant_id=tenant_id) as conn:
        # Generate for tomorrow
        tomorrow = date.today() + timedelta(days=1)
        generate_forecast(tenant_id, tomorrow, conn)

    logger.info("Forecast generation complete", extra={"tenant_id": tenant_id})

@dramatiq.actor(queue_name="default")
def generate_draft_orders(tenant_id: str):
    """
    Task to generate draft purchase orders based on inventory levels and forecasts.
    """
    from services.worker.engines.inventory import generate_draft_orders

    logger.info("Starting inventory optimization", extra={"tenant_id": tenant_id})

    with get_db_connection(tenant_id=tenant_id) as conn:
        generate_draft_orders(tenant_id, conn)

    logger.info("Inventory optimization complete", extra={"tenant_id": tenant_id})
