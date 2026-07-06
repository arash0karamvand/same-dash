# --- Stage 1: build React UI ---
FROM node:20-alpine AS frontend

WORKDIR /app/ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build


# --- Stage 2: Django backend ---
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /app/ui/dist ./ui/dist

RUN chmod +x docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "backend.wsgi:application", "-c", "docker/gunicorn_config.py"]


# --- Stage 3: Nginx (static + reverse proxy) ---
FROM nginx:1.27-alpine AS nginx

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /app/ui/dist /usr/share/nginx/html
