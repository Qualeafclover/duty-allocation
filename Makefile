.PHONY: setup chrome up down test e2e reset

# Local Python environment, Chrome for e2e tests, and Git hooks
setup: chrome
	uv sync --group e2e
	git config core.hooksPath .githooks

# Download Chrome and ChromeDriver: latest, or `make chrome VERSION=142.0.7444.59`
chrome:
	bash scripts/download_chrome.sh $(VERSION)

# Start the app and stream logs: http://localhost:8000
up:
	docker compose up --build

down:
	docker compose down

# Unit tests, inside Docker
test:
	docker compose run --rm backend python -m pytest

# E2E tests, on your machine; run `make up` in another terminal first
# `make e2e V=1` shows the Chrome window and prints each test name
e2e:
	uv run --group e2e pytest e2e/ $(if $(V),-v --headed)

# Rebuild the database from init.sql and start the app; deletes all its data
reset:
	docker compose down -v
	docker compose up --build
