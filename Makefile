.PHONY: up down api worker test desktop
COMPOSE ?= docker compose

up:
	$(COMPOSE) -f infra/docker/docker-compose.yml up --build

down:
	$(COMPOSE) -f infra/docker/docker-compose.yml down -v

api:
	cd services/api && uvicorn app.main:app --reload --port 8000

worker:
	cd services/worker && python -m worker.main

test:
	pytest -q

desktop:
	cd apps/desktop && npm run dev
