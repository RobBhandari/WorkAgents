#!/bin/bash
# Azure App Service startup script for FastAPI Metrics API

cd /home/site/wwwroot

# Start FastAPI with Gunicorn + Uvicorn workers
# -w 4: 4 worker processes (adjust based on your App Service Plan)
# -k uvicorn.workers.UvicornWorker: Use Uvicorn for async support
# --bind 0.0.0.0:8000: Bind to all interfaces on port 8000 (Azure default)
# --timeout 120: 2-minute timeout for long-running requests
# --access-logfile -: Log requests to stdout
# --error-logfile -: Log errors to stdout

gunicorn -w 4 \
  -k uvicorn.workers.UvicornWorker \
  execution.api.app:app \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
