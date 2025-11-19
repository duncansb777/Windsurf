SHELL := /bin/bash

.PHONY: up down logs

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down -v

logs:
	docker compose -f infra/docker-compose.yml logs -f --tail=200

.PHONY: mcp-epic mcp-hca

mcp-epic:
	python3 mcp/mcp-epic-mock/main.py

mcp-hca:
	python3 mcp/mcp-hca-mock/main.py

.PHONY: run-ownership-trigger
.PHONY: run-demo-ui
.PHONY: run-ui

run-ownership-trigger:
	PYTHONPATH=$$(pwd) uvicorn --app-dir services/ownership-trigger/app main:app --reload --port 8001

run-demo-ui:
	PYTHONPATH=$$(pwd) uvicorn --app-dir services/demo-ui/app main:app --reload --port 8000

run-ui:
	# Start Ownership Trigger backend (MCP-backed) and open the HTML UI in the default browser.
	# Backend runs in the foreground here; stop with Ctrl+C when done.
	PYTHONPATH=$$(pwd) uvicorn --app-dir services/ownership-trigger/app main:app --reload --port 8001 & \
	  sleep 2 && open ./agentic-control-demo.html; \
	  wait

.PHONY: help
help:
	@echo "make up                # start infra (NATS, Postgres, Jaeger, Prometheus, Grafana)"
	@echo "make mcp-epic          # run Epic stdio MCP mock"
	@echo "make mcp-hca           # run HCA stdio MCP mock"
	@echo "make run-ownership-trigger  # run Ownership Trigger service on :8001"
	@echo "make run-demo-ui         # run Demo Website on :8000"
	@echo "make run-ui             # run Ownership Trigger + open agentic-control-demo.html in browser"
	@echo "make gen-csv          # generate dummy CSV data under data/csv"
	@echo "make db-fresh         # generate CSVs and recreate DB (destroys pgdata volume)"

.PHONY: gen-csv db-fresh

gen-csv:
	python3 data/generate_csv.py

db-fresh: down gen-csv
	docker compose -f infra/docker-compose.yml up -d
