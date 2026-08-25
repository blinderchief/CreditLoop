# Single-image deploy: build the SPA, then serve everything from FastAPI.
# ---- stage 1: build the frontend ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: python backend that also serves the built SPA ----
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync --no-dev
COPY backend/ /app/backend/
COPY --from=web /web/dist /app/frontend/dist

ENV PORT=8137
EXPOSE 8137
# On boot the API creates the DB and runs the loop once to populate the dashboard.
CMD ["sh", "-c", "uv run uvicorn app.api:app --host 0.0.0.0 --port ${PORT}"]
