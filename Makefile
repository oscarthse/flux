.PHONY: help sim etl api worker forecasts test test-unit test-integration test-rls test-cov lint typecheck security clean-test

help:
	@echo "Flux Platform - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "Data Pipeline:"
	@echo "  make sim          - Run restaurant simulator (30 days)"
	@echo "  make etl          - Load simulator data into database"
	@echo ""
	@echo "Services:"
	@echo "  make api          - Start FastAPI server"
	@echo "  make worker       - Start Dramatiq worker"
	@echo "  make forecasts    - Run forecasting engine"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests (fast)"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-rls     - Run RLS security tests"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint         - Run ruff linter"
	@echo "  make typecheck    - Run mypy type checker"
	@echo "  make security     - Run bandit security scan"
	@echo "  make quality      - Run all quality checks"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean-test   - Remove test artifacts"

# Data Pipeline
sim:
	uv run python scripts/run_sim.py

etl:
	uv run python src/etl/ingest.py

# Services
api:
	uv run uvicorn services.api.main:app --reload --port 8000

worker:
	uv run python services/worker/run_worker.py

forecasts:
	uv run python scripts/run_forecasting.py

# Testing
test:
	uv run pytest -v

test-unit:
	uv run pytest tests/unit/ -v --tb=short

test-integration:
	uv run pytest tests/integration/ -v --tb=short

test-rls:
	uv run pytest -m rls -v

test-cov:
	uv run pytest --cov=services --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

test-fast:
	uv run pytest tests/unit/ -x --tb=short

# Code Quality
lint:
	uv run ruff check services/ src/ tests/

lint-fix:
	uv run ruff check --fix services/ src/ tests/

typecheck:
	uv run mypy services/ src/

security:
	uv run bandit -r services/ src/ -c pyproject.toml

quality: lint typecheck security
	@echo "✅ All quality checks passed!"

# Cleanup
clean-test:
	rm -rf .pytest_cache
