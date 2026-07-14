# --- Stage 1: build the React SPA -------------------------------------------------
FROM node:20-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
# Vite emits into ../src/moe/web_dist (see vite.config.ts)
RUN npm run build

# --- Stage 2: python runtime ------------------------------------------------------
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    MOE_DASHBOARD_HOST=0.0.0.0 \
    MOE_DASHBOARD_PORT=8848 \
    MOE_DB_PATH=/data/moe.db \
    MATERIALS_DIR=/data/materials

COPY pyproject.toml README.md ./
COPY src/ ./src/
# Bring in the built SPA so `pip install` bundles the dashboard into the wheel/package
COPY --from=web /app/src/moe/web_dist ./src/moe/web_dist

RUN pip install --no-cache-dir . && mkdir -p /data

EXPOSE 8848
VOLUME ["/data"]

# Default: run the management dashboard. Override the entrypoint for `moe-mcp` /
# `moe-ingest` (e.g. `docker run ... moe-ingest doctor`).
CMD ["moe-dashboard"]
