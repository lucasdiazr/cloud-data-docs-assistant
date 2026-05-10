# Makefile — atajos de desarrollo para cloud-data-docs-assistant
# Uso: `make <target>`. Lista de targets: `make help`.

.PHONY: help install lint format test docker-up docker-down clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependencias y hooks de pre-commit
	uv sync
	uv run pre-commit install || true

lint: ## Ejecuta ruff (lint) y mypy
	uv run ruff check .
	uv run mypy src

format: ## Formatea el código con ruff
	uv run ruff format .
	uv run ruff check --fix .

test: ## Ejecuta los tests con pytest
	uv run pytest

docker-up: ## Levanta servicios (PostgreSQL + pgvector)
	docker compose up -d
	@echo "Esperando a que PostgreSQL esté listo..."
	@until docker compose exec -T postgres pg_isready -U $${POSTGRES_USER:-postgres} >/dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL listo."

docker-down: ## Apaga los servicios Docker
	docker compose down

clean: ## Limpia cachés y artefactos de build
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
