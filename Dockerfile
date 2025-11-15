# Neurosurgical DCS Hybrid - Production Dockerfile
# Multi-stage build for optimal image size

# Stage 1: Builder
FROM python:3.9-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment and install dependencies
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY src/ ./src/
COPY api/ ./api/
COPY frontend/ ./frontend/
COPY pytest.ini .
COPY requirements.txt .

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 dcsapp && \
    chown -R dcsapp:dcsapp /app && \
    chown -R dcsapp:dcsapp /opt/venv

# Set Python path and virtual environment
ENV PYTHONPATH=/app
ENV PATH="/opt/venv/bin:$PATH"

USER dcsapp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/system/health || exit 1

# Start API with Gunicorn
CMD ["gunicorn", "api.app:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "/app/logs/access.log", \
     "--error-logfile", "/app/logs/error.log", \
     "--log-level", "info"]
