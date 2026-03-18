FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libcurl4-openssl-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist backend/app/static
RUN pip install --no-cache-dir -e backend/
ENV DATABASE_DIR=/app/data
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
