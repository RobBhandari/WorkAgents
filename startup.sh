#!/bin/bash
# Azure App Service startup script for FastAPI Metrics API

cd /home/site/wwwroot

echo "=== Observatory API startup ==="

# Install packages if not already installed (handles both fresh deploy and restart)
if [ -f requirements.txt ]; then
  echo "Installing Python packages..."
  pip install --quiet -r requirements.txt
  echo "Packages installed."
fi

echo "Starting uvicorn..."
uvicorn execution.api.app:app --host 0.0.0.0 --port 8000
