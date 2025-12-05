#!/usr/bin/env python3
"""
Flux Platform - Dramatiq Worker Entry Point

This script starts the Dramatiq worker process that handles background tasks
like POS data ingestion, forecast generation, and draft order creation.
"""
import os
import sys
import dramatiq
from dramatiq.cli import main

# Ensure the app directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import tasks to register them with the broker
from services.worker import tasks

if __name__ == "__main__":
    # Start the Dramatiq worker
    # This will process tasks defined in services/worker/tasks.py
    sys.argv = [
        "dramatiq",
        "services.worker.tasks",
        "--processes", "1",
        "--threads", "2"
    ]
    main()
