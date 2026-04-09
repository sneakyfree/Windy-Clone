# ── Stage 1: Build frontend ──
FROM node:20-alpine AS frontend-build

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── Stage 2: Python API ──
FROM python:3.12-slim AS api

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]"

# Copy API source
COPY api/ ./api/

# Copy built frontend into static serving directory
COPY --from=frontend-build /app/web/dist ./web/dist

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8400

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8400/health || exit 1

# Run with uvicorn
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8400", "--workers", "2"]
