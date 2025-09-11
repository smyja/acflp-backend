# Multi-stage Dockerfile for FastAPI application
# Optimized for production with security and performance best practices

# ============================================================================
# Base stage - Common dependencies and setup
# ============================================================================
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    gcc \
    netcat-traditional \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Install uv for faster dependency management
RUN pip install uv

# ============================================================================
# Dependencies stage - Install Python dependencies
# ============================================================================
FROM base AS dependencies

# Copy dependency files
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies
RUN uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install -e '.[dev]'

# ============================================================================
# Development stage - For local development
# ============================================================================
FROM dependencies AS development

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================================
# Test stage - For running tests
# ============================================================================
FROM base AS test

# Copy dependency files
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies
RUN uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install -e '.[dev]' \
    && uv pip install pytest-xdist pytest-benchmark locust

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure app directory is writable for runtime-generated data
RUN mkdir -p /app/crudadmin_data && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Set test environment
ENV ENVIRONMENT=testing

# Default command for testing
CMD ["pytest", "tests/", "-v", "--cov=src/app", "--cov-report=term-missing"]

# ============================================================================
# Production dependencies stage - Minimal production dependencies
# ============================================================================
FROM base AS prod-dependencies

# Copy dependency files (include README for build metadata)
COPY pyproject.toml uv.lock* README.md ./

# Install only production dependencies
RUN uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install .

# ============================================================================
# Production stage - Optimized for production deployment
# ============================================================================
FROM python:3.11-slim AS production

# Set environment variables for production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production \
    PYTHONPATH="/app/src:$PYTHONPATH"

# Install only runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from dependencies stage
COPY --from=prod-dependencies /opt/venv /opt/venv

# Set work directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=appuser:appuser src/ ./src/
# Alembic configuration and migrations live under src/ in this repo
COPY --chown=appuser:appuser src/alembic.ini ./alembic.ini
COPY --chown=appuser:appuser src/migrations/ ./migrations/

# Create necessary directories
RUN mkdir -p /app/logs \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Production command with Gunicorn
CMD ["gunicorn", "src.app.main:app", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--workers", "4", \
    "--bind", "0.0.0.0:8000", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "--max-requests", "1000", \
    "--max-requests-jitter", "100", \
    "--preload"]
