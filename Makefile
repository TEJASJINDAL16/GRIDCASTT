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
        archive backfill-vintages measure baseline test docker docker-test clean \
        tune model ablate calibrate train daily retry report model-card holdout audit catch-up replay diagnose-linear

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
	  echo "libomp missing - LightGBM will fail to load."; \
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

# --- daily archive (PLANNING 5d - unrecoverable if delayed) ---------------

archive: setup  ## Archive a weather forecast vintage and a demand-revision snapshot
	$(PY) scripts/archive_daily.py $(ARGS)

backfill-vintages: setup  ## Recover past forecast vintages (leads 1-7, 2022+)
	$(PY) scripts/backfill_vintages.py $(ARGS)

catch-up:  ## Merge a missing demand/weather range (ARGS="--start YYYY-MM-DD")
	$(PY) scripts/catch_up.py $(ARGS)

# --- analysis ------------------------------------------------------------

measure: setup  ## Step-0 measurements -> reports/step0_measurements.md
	$(PY) scripts/measure_step0.py $(ARGS)

baseline: setup  ## Score four baselines on twelve monthly folds (cached data only)
	$(PY) scripts/backtest_baselines.py

tune:  ## Select model parameters on measured pre-test targets
	$(PY) scripts/tune.py

model:  ## Evaluate the frozen hybrid against all four baselines
	$(PY) scripts/backtest_model.py

ablate:  ## Measure feature and estimation-policy contributions
	$(PY) scripts/ablate.py

diagnose-linear:  ## Check linear zone composition on reserved validation only
	$(PY) scripts/diagnose_linear.py

calibrate:  ## Derive fixed trigger thresholds and promotion tolerances
	$(PY) scripts/calibrate.py

replay:  ## Exercise routing, promotion and cooldown on recorded rows
	$(PY) scripts/replay.py

train:  ## Initialize an approved champion, or retain a rejected candidate
	$(PY) scripts/train.py

daily:  ## Run the complete daily forecast job
	$(PY) scripts/daily.py $(ARGS)

retry:  ## Make one weather retry when eligible
	$(PY) scripts/daily.py --retry $(ARGS)

report:  ## Render the static dashboard
	$(PY) scripts/report.py

model-card:  ## Generate the evidence-based model card
	$(PY) scripts/model_card.py

holdout:  ## Evaluate the reserved final period once
	$(PY) scripts/holdout.py

audit:  ## Check requirements against recorded evidence
	$(PY) scripts/audit.py

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

.PHONY: refine-model
refine-model:  ## Compare availability-safe demand-history candidates
	$(PY) scripts/refine_model.py

.PHONY: configure-drive
configure-drive:  ## Import a downloaded Desktop OAuth client JSON (ARGS=path)
	$(PY) scripts/configure_drive.py $(ARGS)

.PHONY: history-metrics history-holdout
history-metrics:  ## Full metric breakdown for the frozen history candidate
	$(PY) scripts/evaluate_history.py

history-holdout:  ## Evaluate the fixed history candidate on the reserved year once
	$(PY) scripts/evaluate_history.py --final-holdout
