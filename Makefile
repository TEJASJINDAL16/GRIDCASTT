# gridcast
# Run `make setup` once, then everything else works.

VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

.PHONY: help setup weather em clean

help:  ## Show available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*##"};{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

$(VENV):
	python3 -m venv $(VENV)

setup: $(VENV)  ## Create the virtual environment and install dependencies
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@echo "Ready. Run 'make weather' or 'make em'."

weather: setup  ## Verify Open-Meteo (no API key needed)
	$(PY) scripts/check_weather.py

em: setup  ## Verify Electricity Maps (needs .env)
	$(PY) scripts/verify_em.py

clean:  ## Remove the virtual environment and caches
	rm -rf $(VENV)
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

backfill: setup  ## Pull and cache the full demand history (run once)
	$(PY) scripts/backfill.py $(ARGS)
