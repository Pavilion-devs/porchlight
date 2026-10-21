# Porchlight: common commands. Run `make` to see them.
PY      := .venv/bin/python
PORT    ?= 8000
SCENARIO ?= full_day

.DEFAULT_GOAL := help
.PHONY: help setup check run run-offline demo test telegram

help:  ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

setup:  ## Create .venv, install the backend, create .env from the example
	@test -d .venv || python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r backend/requirements.txt
	@test -f .env || (cp .env.example .env && echo "Created .env. Fill it in (see README).")
	@echo "Done. Next: fill in .env, then run 'make check'."

check:  ## Check .env, the Ring sandbox, Bedrock and Telegram
	$(PY) scripts/doctor.py

run:  ## Start the backend: live Ring stream + Bedrock (http://localhost:8000)
	cd backend && ../$(PY) -m uvicorn porchlight.app:app --port $(PORT)

run-offline:  ## Start the backend with no Ring stream and no AWS (replay demos only)
	cd backend && WATCHER_ENABLED=false USE_AGENT=false ../$(PY) -m uvicorn porchlight.app:app --port $(PORT)

demo:  ## Play a scripted day on the running backend (SCENARIO=full_day|package|repeat_visitor|routine_missed|night_activity)
	@curl -s -X POST localhost:$(PORT)/api/demo/$(SCENARIO) && echo

test:  ## Run the backend tests (no AWS or Ring calls)
	cd backend && ../$(PY) -m pytest -q

telegram:  ## Find your Telegram chat ID, save it to .env, send a test message
	$(PY) scripts/telegram_setup.py
