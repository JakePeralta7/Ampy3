# --- Frontend builder ---
FROM node:alpine AS web-builder

RUN npm i -g pnpm@11.16.0

WORKDIR /app/web

# Install dependencies first (cached until lockfile changes)
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
ENV PNPM_CONFIG_STRICT_DEP_BUILDS=false
RUN CI=true pnpm install --frozen-lockfile

# Copy source files (excluding node_modules via .dockerignore)
COPY web/src ./src
COPY web/public ./public
COPY web/index.html web/tsconfig.json web/vite.config.ts web/biome.json ./

RUN pnpm run build

# Remove dev dependencies to reduce layer size
RUN rm -rf node_modules


# --- Python dependency builder ---
FROM python:slim AS builder

WORKDIR /app

# Install dependencies first (cached until pyproject.toml changes)
COPY pyproject.toml ./
# Stub src so pip can resolve the editable package; deleted after install
RUN mkdir -p src/app && touch src/app/__init__.py
RUN pip install --no-cache-dir --prefer-binary --prefix=/install . && rm -rf src

# Copy source and alembic after deps so code changes don't invalidate pip layer
COPY src/ ./src/
COPY alembic/ ./alembic/


# --- Base production image (shared by web + worker) ---
FROM python:slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Run as a non-root user inside the container
RUN groupadd --system app && useradd --system --gid app --home-dir /app appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY pyproject.toml ./
COPY alembic/ ./alembic/
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV APP_ENV=production

USER appuser

# --- Web image (API + SPA) ---
FROM base AS web

COPY --from=web-builder /app/web/dist /app/web/dist
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Worker image (no frontend) ---
FROM base AS worker
CMD ["celery", "-A", "app.worker.app", "worker"]
