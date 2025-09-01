# Enterprise FastAPI Development Makefile
# Provides standardized commands for development, testing, and deployment

.PHONY: help install install-dev clean test test-unit test-integration test-e2e test-coverage
.PHONY: lint format type-check security-check quality-check pre-commit
.PHONY: docker-build docker-test docker-prod docker-clean
.PHONY: db-upgrade db-downgrade db-reset db-seed
.PHONY: run run-dev run-prod run-worker
.PHONY: docs docs-serve deploy-staging deploy-prod
.PHONY: venv venv-remove python-version

# Default target
help: ## Show this help message
	@echo "Enterprise FastAPI Development Commands"
	@echo "======================================"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# =============================================================================
# Tool autodetection (fallback if `uv` is not installed)
# =============================================================================

SHELL := /bin/bash
UV_BIN := $(shell command -v uv 2>/dev/null)
UV_PIP := $(if $(UV_BIN),uv pip,pip)

# =============================================================================
# Environment Setup
# =============================================================================

install: ## Install production dependencies
	$(UV_PIP) install .

install-dev: ## Install development dependencies
	$(UV_PIP) install -e ".[dev]"

clean: ## Clean up cache files and build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf dist/
	rm -rf build/

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/ -v -m "unit or not (integration or e2e)"

test-integration: ## Run integration tests only
	pytest tests/ -v -m "integration"

test-e2e: ## Run end-to-end tests only
	pytest tests/ -v -m "e2e"

test-coverage: ## Run tests with coverage report
	pytest tests/ \
		--cov=src/app \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		-v

test-parallel: ## Run tests in parallel
	pytest tests/ -n auto -v

test-watch: ## Run tests in watch mode
	pytest-watch -- tests/ -v

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run linting checks
	ruff check src tests

format: ## Format code
	ruff format src tests

format-check: ## Check code formatting
	ruff format src tests --check

type-check: ## Run type checking
	mypy src --config-file pyproject.toml

security-check: ## Run security checks
	bandit -r src/ -f json
	safety check --json

quality-check: lint format-check type-check security-check ## Run all quality checks

pre-commit: quality-check test-unit ## Run pre-commit checks

# =============================================================================
# Docker Commands
# =============================================================================

docker-build: ## Build Docker image for development
	docker build --target development -t acflp-backend:dev .

docker-build-prod: ## Build Docker image for production
	docker build --target production -t acflp-backend:prod .

docker-build-test: ## Build Docker image for testing
	docker build --target test -t acflp-backend:test .

docker-test: docker-build-test ## Run tests in Docker
	docker run --rm acflp-backend:test

docker-security: ## Run security scan on Docker image
	docker build --target security -t acflp-backend:security .
	docker run --rm acflp-backend:security

docker-compose-up: ## Start services with Docker Compose
	docker-compose up -d

docker-compose-test: ## Run tests with Docker Compose
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

docker-compose-down: ## Stop Docker Compose services
	docker-compose down -v

docker-clean: ## Clean up Docker images and containers
	docker system prune -f
	docker image prune -f

# =============================================================================
# Database Commands
# =============================================================================

db-upgrade: ## Run database migrations
	alembic upgrade head

db-downgrade: ## Rollback database migration
	alembic downgrade -1

db-reset: ## Reset database (WARNING: destroys data)
	alembic downgrade base
	alembic upgrade head

db-seed: ## Seed database with initial data
	python src/scripts/create_first_superuser.py
	python src/scripts/create_first_tier.py

db-revision: ## Create new database migration
	@read -p "Enter migration message: " message; \
	alembic revision --autogenerate -m "$$message"

# =============================================================================
# Development Server
# =============================================================================

run: ## Run development server
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-dev: install-dev db-upgrade ## Setup and run development environment
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod: ## Run production server
	gunicorn app.main:app \
		--worker-class uvicorn.workers.UvicornWorker \
		--workers 4 \
		--bind 0.0.0.0:8000 \
		--access-logfile - \
		--error-logfile - \
		--log-level info

run-worker: ## Run background worker
	arq app.core.worker.settings.WorkerSettings

# =============================================================================
# Documentation
# =============================================================================

docs: ## Generate API documentation
	@echo "API documentation available at: http://localhost:8000/docs"
	@echo "Alternative docs at: http://localhost:8000/redoc"

docs-serve: run ## Serve documentation (alias for run)

# =============================================================================
# Performance and Load Testing
# =============================================================================

load-test: ## Run load tests with Locust
	locust -f tests/load/locustfile.py --host=http://localhost:8000

benchmark: ## Run performance benchmarks
	pytest tests/ -m "performance" --benchmark-only

# =============================================================================
# CI/CD and Deployment
# =============================================================================

ci-test: ## Run CI test suite
	make quality-check
	make test-coverage
	make docker-test

ci-security: ## Run CI security checks
	make security-check
	make docker-security

deploy-staging: ## Deploy to staging environment
	@echo "Deploying to staging..."
	# Add staging deployment commands here

deploy-prod: ## Deploy to production environment
	@echo "Deploying to production..."
	# Add production deployment commands here

# =============================================================================
# Monitoring and Health Checks
# =============================================================================

health-check: ## Check application health
	curl -f http://localhost:8000/api/v1/health || exit 1

metrics: ## Display application metrics
	curl -s http://localhost:8000/metrics

# =============================================================================
# Development Utilities
# =============================================================================

shell: ## Start interactive Python shell with app context
	python -c "from app.main import app; import IPython; IPython.embed()"

requirements: ## Generate requirements.txt from pyproject.toml
	@if command -v uv >/dev/null 2>&1; then \
		uv pip compile pyproject.toml -o requirements.txt; \
	elif command -v pip-compile >/dev/null 2>&1; then \
		pip-compile pyproject.toml -o requirements.txt; \
	else \
		echo "Install 'uv' or 'pip-tools' (pip-compile) to generate requirements.txt"; \
	fi

requirements-dev: ## Generate dev requirements
	@if command -v uv >/dev/null 2>&1; then \
		uv pip compile pyproject.toml --extra dev -o requirements-dev.txt; \
	elif command -v pip-compile >/dev/null 2>&1; then \
		pip-compile pyproject.toml --extra dev -o requirements-dev.txt; \
	else \
		echo "Install 'uv' or 'pip-tools' (pip-compile) to generate requirements-dev.txt"; \
	fi

update-deps: ## Update all dependencies
	$(UV_PIP) install --upgrade -e ".[dev]"

check-deps: ## Check for dependency vulnerabilities
	safety check

pip-audit: ## Run pip-audit for security vulnerabilities
	pip-audit

# =============================================================================
# Git Hooks and Pre-commit
# =============================================================================

GIT_HOOKS_PATH := $(shell git config --get core.hooksPath 2>/dev/null)

install-hooks: ## Install git hooks
	@if [ -n "$(GIT_HOOKS_PATH)" ]; then \
		echo "[info] git core.hooksPath is set to '$(GIT_HOOKS_PATH)'."; \
		echo "[info] Using .githooks wrapper scripts instead of 'pre-commit install'."; \
		echo "[info] Run: make install-githooks"; \
		exit 0; \
	fi
	pre-commit install
	pre-commit install --hook-type commit-msg
	pre-commit install --hook-type pre-push

install-githooks: ## Copy .githooks/* into configured core.hooksPath
	@if [ -z "$(GIT_HOOKS_PATH)" ]; then \
		echo "[error] core.hooksPath is not set. Either run 'git config core.hooksPath .githooks' or unset it and use 'make install-hooks'."; \
		exit 1; \
	fi
	mkdir -p "$(GIT_HOOKS_PATH)"
	cp -f .githooks/* "$(GIT_HOOKS_PATH)/"
	chmod +x "$(GIT_HOOKS_PATH)/pre-commit" "$(GIT_HOOKS_PATH)/pre-push" "$(GIT_HOOKS_PATH)/commit-msg"
	echo "[ok] Installed git hooks to $(GIT_HOOKS_PATH)"

run-hooks: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# =============================================================================
# Environment Variables
# =============================================================================

ENVIRONMENT ?= local
SECRET_KEY ?= dev-secret-key-change-in-production
POSTGRES_URL ?= postgresql://postgres:postgres@localhost:5432/acflp_dev
REDIS_URL ?= redis://localhost:6379/0

# Export environment variables for commands
export ENVIRONMENT
export SECRET_KEY
export POSTGRES_URL
export REDIS_URL
VENV ?= .venv

# Create a local Python 3.11 virtual environment
venv: ## Create a Python 3.11 virtual environment in .venv
	@set -e; \
	if command -v python3.11 >/dev/null 2>&1; then PY=python3.11; \
	elif command -v python3 >/dev/null 2>&1; then PY=python3; \
	else PY=python; fi; \
	$$PY -V; \
	$$PY -m venv $(VENV); \
	. $(VENV)/bin/activate; \
	python -m pip install --upgrade pip setuptools wheel; \
	echo "Virtualenv created at $(VENV). Activate with: source $(VENV)/bin/activate";

# Remove the virtual environment
venv-remove: ## Remove the virtual environment
	rm -rf $(VENV)

# Print the Python version in the current shell
python-version: ## Print Python version and path
	@python -V && which python
