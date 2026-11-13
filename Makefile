PY ?= .venv/bin/python
DB ?= data/goe.db

.PHONY: help setup doctor ingest scan test test-network handoff replay cases web clean-dist

help:
	@echo "make setup      - create venv and install dependencies"
	@echo "make doctor     - environment/data/provider health check"
	@echo "make ingest     - backfill 10y prices + all indicator series"
	@echo "make scan       - run the full pipeline and write reports/exports"
	@echo "make test       - offline test suite"
	@echo "make test-network - provider tests against live endpoints"
	@echo "make cases      - historical point-in-time case validation"
	@echo "make replay     - 3-year point-in-time replay"
	@echo "make handoff    - hand the top opportunities to investment-agent"

setup:
	UV_CACHE_DIR=$$PWD/.uvcache ~/.local/bin/uv venv .venv --python 3.12
	UV_CACHE_DIR=$$PWD/.uvcache ~/.local/bin/uv pip install --python $(PY) -r requirements.txt

doctor:
	$(PY) -m goe.cli doctor

ingest:
	$(PY) -m goe.cli ingest --mode backfill

scan:
	$(PY) -m goe.cli scan

test:
	$(PY) -m pytest tests -q -m "not network"

test-network:
	$(PY) -m pytest tests -q -m network

cases:
	$(PY) -m goe.cli replay --cases

replay:
	$(PY) -m goe.cli replay --start 2024-01-01 --step 21

handoff:
	$(PY) -m goe.cli handoff --ia-path $$GOE_IA_PATH --limit 3 --dry-run

web:
	$(PY) -m goe.cli web

clean-dist:
	rm -rf reports exports/ia_runs .pytest_cache
