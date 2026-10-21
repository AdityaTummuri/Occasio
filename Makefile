VENV ?= .venv
PY := $(VENV)/bin/python

.PHONY: install run test lint format typecheck size demo

install:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

run:
	$(PY) -m uvicorn occasio.api.app:create_app --factory --host 127.0.0.1 --port 8000

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

typecheck:
	$(PY) -m mypy src/occasio

size:
	du -sh --exclude=.git .
	git count-objects -vH
