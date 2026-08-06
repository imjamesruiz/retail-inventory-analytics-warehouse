.PHONY: install lint format test test-unit test-integration \
	ingest-fixtures ingest-live load-snowflake \
	dbt-deps dbt-debug dbt-build dbt-docs \
	dashboard pipeline metrics clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev,dbt]"
	$(VENV)/bin/pre-commit install

lint:
	$(VENV)/bin/ruff check src tests dashboard

format:
	$(VENV)/bin/ruff format src tests dashboard
	$(VENV)/bin/ruff check --fix src tests dashboard

test: test-unit

test-unit:
	$(VENV)/bin/pytest tests/unit -v

test-integration:
	$(VENV)/bin/pytest tests/integration -v -m integration

ingest-fixtures:
	$(PY) -m inventory_pipeline.cli ingest --source-mode fixture

ingest-live:
	$(PY) -m inventory_pipeline.cli ingest --source-mode live

load-snowflake:
	$(PY) -m inventory_pipeline.cli load-snowflake

dbt-deps:
	cd dbt_inventory && ../$(VENV)/bin/dbt deps --profiles-dir .

dbt-debug:
	cd dbt_inventory && ../$(VENV)/bin/dbt debug --profiles-dir .

dbt-build:
	cd dbt_inventory && ../$(VENV)/bin/dbt build --profiles-dir .

dbt-docs:
	cd dbt_inventory && ../$(VENV)/bin/dbt docs generate --profiles-dir . && ../$(VENV)/bin/dbt docs serve --profiles-dir .

dashboard:
	$(VENV)/bin/streamlit run dashboard/app.py

pipeline:
	$(PY) -m inventory_pipeline.cli pipeline --source-mode fixture

metrics:
	$(PY) -m inventory_pipeline.cli metrics

clean:
	rm -rf $(VENV) dbt_inventory/target dbt_inventory/dbt_packages dbt_inventory/logs
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
