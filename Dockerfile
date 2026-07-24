# --- Frontend builder ---
FROM node:26-alpine AS web-builder

RUN npm i -g pnpm@11.16.0

WORKDIR /app/web

# Install dependencies first (cached until lockfile changes)
COPY web/package.json web/pnpm-lock.yaml ./
ENV PNPM_CONFIG_STRICT_DEP_BUILDS=false
RUN CI=true pnpm install --frozen-lockfile

# Copy source files (excluding node_modules via .dockerignore)
COPY web/src ./src
COPY web/index.html web/tsconfig.json web/vite.config.ts web/tailwind.config.js web/postcss.config.js web/biome.json ./

RUN pnpm run build

# Remove dev dependencies to reduce layer size
RUN rm -rf node_modules


# --- Python dependency builder ---
FROM python:3.14-slim AS builder

WORKDIR /app

# Install dependencies first (cached until pyproject.toml changes)
COPY pyproject.toml ./
# Need to copy src for setuptools to find packages when installing in editable mode
COPY src/ ./src/
RUN pip install --no-cache-dir --prefer-binary --prefix=/install -e "."

# Copy alembic migrations after install so code changes don't invalidate the pip layer
COPY alembic/ ./alembic/


# --- Base production image (shared by web + worker) ---
FROM python:3.14-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY pyproject.toml ./
COPY alembic/ ./alembic/
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV APP_ENV=production

# --- Web image (API + SPA) ---
FROM base AS web

COPY --from=web-builder /app/web/dist /app/web/dist
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Worker image (no frontend) ---
FROM base AS worker
CMD ["celery", "-A", "src.app.tasks", "worker"]
