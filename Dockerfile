# Multi-stage build for mess management system
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs media staticfiles && \
    chown -R appuser:appuser /app

# Collect static files
RUN python manage.py collectstatic --noinput

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "mess_management.wsgi:application"]

# Development stage
FROM base as development

USER root

# Install development dependencies
RUN pip install \
    ipython \
    django-debug-toolbar \
    pytest-django \
    black \
    flake8

USER appuser

# Development command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Production stage
FROM base as production

# Production-specific configurations
ENV DJANGO_SETTINGS_MODULE=mess_management.settings.production

# Copy production configuration
COPY docker/gunicorn.conf.py /app/

# Use gunicorn with custom config
CMD ["gunicorn", "--config", "gunicorn.conf.py", "mess_management.wsgi:application"]