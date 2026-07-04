VENV := .venv
ifeq ($(OS),Windows_NT)
PY := $(VENV)/Scripts/python.exe
else
PY := $(VENV)/bin/python
endif

.PHONY: venv install test test-all test-integration coverage lint format clean

venv:            ## Crea il virtualenv (.venv)
	python -m venv $(VENV)

install:         ## Installa il package in editable mode con le dipendenze dev
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

test:            ## Esegue i test unit (offline, esclude gli integration)
	$(PY) -m pytest

test-integration: ## Esegue SOLO i test che toccano Internet Archive reale
	$(PY) -m pytest -m integration

test-all:        ## Esegue tutta la suite, integration inclusi
	$(PY) -m pytest -m ""

coverage:        ## Esegue i test con il gate di copertura (100% righe+branch)
	$(PY) -m coverage run -m pytest
	$(PY) -m coverage report

lint:            ## Controlli statici ruff
	$(PY) -m ruff check src tests

format:          ## Formatta il codice con ruff
	$(PY) -m ruff format src tests

clean:           ## Rimuove artefatti di build e cache
	$(PY) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['build', 'dist', '.pytest_cache', '.ruff_cache']]"
