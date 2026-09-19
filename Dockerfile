# --- Frontend builder ---
FROM node:alpine AS web-builder

RUN npm i -g pnpm@12.4.2

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

# Install cryptography from binary wheels to avoid requiring Rust toolchain
# (wheels available for manylinux; only falls back to source on unsupported archs)
WORKDIR /app

# Install dependencies only (cached until pyproject.toml changes)
# Extract dependencies from pyproject.toml and install them without the package
COPY pyproject.toml ./
RUN python -c "import tomllib; data=tomllib.load(open('pyproject.toml','rb')); deps=data['project']['dependencies']; print('\n'.join(deps))" > /tmp/deps.txt && pip install --no-cache-dir --prefer-binary --only-binary=cryptography --prefix=/install -r /tmp/deps.txt && rm /tmp/deps.txt


# --- Base production image (shared by web + worker) ---
FROM python:slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Run as a non-root user inside the container
RUN groupadd --system app && useradd --system --gid app --home-dir /app appuser

WORKDIR /app

# Copy installed dependencies from builder (without the package source)
COPY --from=builder /install /usr/local
# Copy source code and alembic directly from host (avoids builder cache issues)
COPY src/ ./src
COPY alembic/ ./alembic
COPY pyproject.toml ./

# Install the package in editable mode so code changes are reflected
RUN pip install --no-cache-dir -e .

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
