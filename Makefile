.PHONY: install up down sim etl verify test all clean

install:
	uv sync

up:
	docker-compose up -d

down:
	docker-compose down

sim:
	uv run scripts/run_sim.py

etl:
	uv run src/etl/ingest.py

verify:
	uv run scripts/verify_db.py

test:
	uv run pytest

dashboard:
	uv run streamlit run src/dashboard/app.py

all: up sim etl verify

clean:
	rm -rf output_data/*.csv
	rm -rf __pycache__
	rm -rf .pytest_cache
