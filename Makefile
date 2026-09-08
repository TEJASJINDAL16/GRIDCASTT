# gridcast
# Every entry point is a target here (PLANNING 8). `make setup` works on a
# fresh clone.

PYTHON_VERSION := 3.12
VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
DVC    := $(VENV)/bin/dvc

IMAGE  := gridcast
UNAME  := $(shell uname -s)

.PHONY: help setup deps check-libomp weather em backfill backfill-weather \
        archive measure test docker docker-test clean

help:  ## Show available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*##"};{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- environment ---------------------------------------------------------
# Built from python3.12 explicitly. Bare `python3` is whatever the machine
# happens to point at; the environment is one of the five pins (PLANNING 14)
# and a floating interpreter pins nothing.

$(VENV):
	@command -v python$(PYTHON_VERSION) >/dev/null 2>&1 || { \
	  echo "python$(PYTHON_VERSION) not found."; \
	  echo "macOS:  brew install python@$(PYTHON_VERSION)"; exit 1; }
	python$(PYTHON_VERSION) -m venv $(VENV)

check-libomp:  ## macOS only: LightGBM needs Homebrew libomp at runtime
ifeq ($(UNAME),Darwin)
	@test -f "$$(brew --prefix 2>/dev/null)/opt/libomp/lib/libomp.dylib" || { \
	  echo "libomp missing — LightGBM will fail to load."; \
	  echo "fix:  brew install libomp"; exit 1; }
endif

setup: $(VENV) check-libomp  ## Create the venv (3.12) and install pinned dependencies
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@$(PY) -c "import lightgbm, pandas, dvc, mlflow" \
	  || { echo "dependency import failed"; exit 1; }
	@echo "Ready ($$($(PY) --version)). See 'make help'."

deps: setup  ## Alias for setup

# --- data pulls (need network; see PLANNING 11, 12) -----------------------

weather: setup  ## Probe Open-Meteo: archive depth and forecast shape (no key)
	$(PY) scripts/check_weather.py

em: setup  ## Probe Electricity Maps (needs .env)
	$(PY) scripts/verify_em.py

backfill: setup  ## Pull and cache the full demand history (run once)
	$(PY) scripts/backfill.py $(ARGS)

backfill-weather: setup  ## Pull and cache observed weather history (run once)
	$(PY) scripts/backfill_weather.py $(ARGS)

# --- daily archive (PLANNING 5d — unrecoverable if delayed) ---------------

archive: setup  ## Archive a weather forecast vintage and a demand-revision snapshot
	$(PY) scripts/archive_daily.py $(ARGS)

# --- analysis ------------------------------------------------------------

measure: setup  ## Step-0 measurements -> reports/step0_measurements.md
	$(PY) scripts/measure_step0.py $(ARGS)

# --- checks --------------------------------------------------------------

test: setup  ## Run the invariant tests
	$(PYTEST) -q tests/

# --- container -----------------------------------------------------------

docker:  ## Build the pinned image
	docker build -t $(IMAGE):local .

docker-test: docker  ## Run the invariant tests inside the image
	docker run --rm $(IMAGE):local pytest -q tests/

# --- housekeeping --------------------------------------------------------

clean:  ## Remove the virtual environment and caches
	rm -rf $(VENV)
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -exec rm -rf {} + 2>/dev/null || true
