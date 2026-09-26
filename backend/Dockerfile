FROM node:22-alpine@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS web-build
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend /app/backend
COPY data /app/data
COPY --from=web-build /build/frontend/dist /app/web
ENV DATA_DIR=/app/runtime
RUN mkdir -p /app/runtime && useradd -m -u 10001 workbench && chown -R workbench:workbench /app
USER workbench
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
