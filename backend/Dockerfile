# ==============================================================================
# Production-ready Dockerfile for FastAPI Backend
# ==============================================================================

FROM python:3.11-slim

# Set environment variables:
# 1. Prevent Python from writing .pyc files to disk
# 2. Force stdout/stderr to be unbuffered for instant logging
# 3. Add app directory to Python path
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install basic system tools (curl is useful for container health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python package dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Create a non-root system group and user for security isolation
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Copy backend application source code
COPY app/ ./app/

# Grant the non-root user permissions to the application directory
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the default FastAPI port
EXPOSE 8000

# Execute FastAPI via Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
