FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /web/dist /app/frontend/dist
COPY frontend/public/samples /app/demo-samples
RUN useradd --uid 10001 --create-home demo && mkdir -p /app/persistent/uploads && chown -R demo:demo /app
USER demo
ENV APP_ENV=production DEBUG=false DEMO_ONLY=true \
    DATABASE_URL=sqlite:////app/persistent/demo.db \
    UPLOAD_DIR=/app/persistent/uploads \
    DEMO_SAMPLES_DIR=/app/demo-samples
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
