# =====================================================================
# TINTORA MADRID - DOCKERFILE
# Multi-stage production ready image
# =====================================================================

# Stage 1: Build Node & Tailwind assets
FROM node:22-alpine AS frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tailwind.config.js postcss.config.js ./
COPY static ./static
COPY templates ./templates
COPY apps ./apps
RUN npm run build

# Stage 2: Python environment
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for PostgreSQL, Weasyprint (Cairo/Pango), Gettext
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gettext \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements ./requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/prod.txt

# Copy source code
COPY . .

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /app/static/dist ./static/dist

# Create non-root user for security
RUN addgroup --system tintora && adduser --system --group tintora && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R tintora:tintora /app

USER tintora

EXPOSE 8000

CMD ["/bin/sh", "/app/deploy/render-start.sh"]
