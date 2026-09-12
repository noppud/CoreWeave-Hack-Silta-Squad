# Multi-stage build for Silta CNC manufacturing agent
# Optimized for cadquery/OCP with minimal system dependencies

# --- Stage 1: Build dependencies ---
FROM python:3.12-slim-bookworm AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv
# --locked ensures we use exact versions from uv.lock
# --no-dev excludes development dependencies
RUN uv sync --locked --no-dev --no-install-project

# --- Stage 2: Runtime image ---
FROM python:3.12-slim-bookworm

# Install minimal system dependencies for cadquery/OCP
# OCP (OpenCascade) requires OpenGL and X11 libraries for 3D geometry operations
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglu1-mesa \
        libgomp1 \
        libx11-6 \
        libxext6 \
        libxrender1 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user for runtime
RUN useradd -m -u 1000 silta && \
    mkdir -p /app /tmp/artifacts && \
    chown -R silta:silta /app /tmp/artifacts

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder --chown=silta:silta /app/.venv /app/.venv

# Copy application code
COPY --chown=silta:silta silta/ ./silta/
COPY --chown=silta:silta notebooks/ ./notebooks/
COPY --chown=silta:silta demo/ ./demo/
# The frozen evaluation corpus and the promotion records are read at runtime by
# notebooks/evaluations.py, so they are part of the application, not documentation.
COPY --chown=silta:silta fixtures/ ./fixtures/
COPY --chown=silta:silta policies/ ./policies/
COPY --chown=silta:silta pyproject.toml ./

# Add .venv to PATH
ARG GIT_COMMIT=unknown
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SILTA_ARTIFACT_DIR=/tmp/artifacts \
    SILTA_COMMIT=${GIT_COMMIT}

# Verify cadquery import works
RUN python -c "import cadquery; import marimo; print('Dependencies OK')"

# Switch to non-root user
USER silta

# Cloud Run sets PORT env; default to 8080 for local testing
ENV PORT=8080

# Health check endpoint (marimo provides /health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:' + __import__('os').environ.get('PORT', '8080') + '/health')"

# Image metadata
ARG GIT_COMMIT=unknown
ARG LOCK_HASH=unknown
LABEL org.opencontainers.image.source="https://github.com/finata/silta-squad" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      dev.silta.lock-hash="${LOCK_HASH}" \
      dev.silta.version="1.0.0"

# Run marimo in headless application mode
# --host 0.0.0.0 accepts external connections (Cloud Run requires this)
# --port $PORT uses Cloud Run's assigned port
# --headless disables browser launch and editor UI
CMD ["sh", "-c", "exec uvicorn silta.web:app --host 0.0.0.0 --port $PORT --workers 1"]
