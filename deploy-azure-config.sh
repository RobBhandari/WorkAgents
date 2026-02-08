#!/bin/bash
# Configure Azure Web App Application Settings
# Run this AFTER creating your Azure Web App
#
# ⚠️  SECURITY WARNING:
# This script reads credentials from .env and sends to Azure.
# - Run this ONLY on your secure local machine
# - Do NOT commit this script with hardcoded credentials
# - Do NOT run this on shared/public machines
# - Credentials are sent over HTTPS to Azure

set -e  # Exit on any error

# ============================================================
# Configuration Variables - UPDATE THESE
# ============================================================

RESOURCE_GROUP="metrics-api-rg"          # Your resource group name
WEB_APP_NAME="metrics-api-prod"          # Your web app name

echo ""
echo "============================================================"
echo "Azure Web App Configuration Script"
echo "============================================================"
echo ""
echo "Target: $WEB_APP_NAME (Resource Group: $RESOURCE_GROUP)"
echo ""
echo "⚠️  This script will:"
echo "   1. Read credentials from your .env file"
echo "   2. Upload them to Azure Application Settings"
echo "   3. Credentials will be encrypted in Azure"
echo ""
read -p "Continue? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
  echo "Aborted."
  exit 0
fi
echo ""

# ============================================================
# STEP 1: Set API Credentials (CHANGE THESE!)
# ============================================================

echo "Setting API credentials..."

# Prompt for credentials instead of hardcoding
read -p "API Username [metrics_admin]: " API_USERNAME
API_USERNAME=${API_USERNAME:-metrics_admin}

read -sp "API Password (min 8 chars): " API_PASSWORD
echo ""

if [ ${#API_PASSWORD} -lt 8 ]; then
  echo "ERROR: Password must be at least 8 characters"
  exit 1
fi

az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEB_APP_NAME" \
  --settings \
    API_USERNAME="$API_USERNAME" \
    API_PASSWORD="$API_PASSWORD" \
  --output none

echo "✅ API credentials set"

# ============================================================
# STEP 2: Copy existing credentials from local .env
# ============================================================

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Cannot copy credentials."
  exit 1
fi

echo "Reading credentials from .env (file will not be exposed)..."

# Securely load .env without exposing in process list
set -a  # Auto-export variables
source <(grep -v '^#' .env | grep -v '^$')
set +a

echo "Setting Azure DevOps credentials..."
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEB_APP_NAME" \
  --settings \
    ADO_ORGANIZATION_URL="$ADO_ORGANIZATION_URL" \
    ADO_PROJECT_NAME="$ADO_PROJECT_NAME" \
    ADO_PAT="$ADO_PAT" \
  --output none
echo "✅ Azure DevOps configured"

echo "Setting ArmorCode credentials..."
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEB_APP_NAME" \
  --settings \
    ARMORCODE_API_KEY="$ARMORCODE_API_KEY" \
    ARMORCODE_BASE_URL="$ARMORCODE_BASE_URL" \
    ARMORCODE_ENVIRONMENT="$ARMORCODE_ENVIRONMENT" \
    ARMORCODE_PRODUCTS="$ARMORCODE_PRODUCTS" \
    ARMORCODE_EMAIL_RECIPIENTS="$ARMORCODE_EMAIL_RECIPIENTS" \
    ARMORCODE_BASELINE_DATE="$ARMORCODE_BASELINE_DATE" \
    ARMORCODE_TARGET_DATE="$ARMORCODE_TARGET_DATE" \
    ARMORCODE_REDUCTION_GOAL="$ARMORCODE_REDUCTION_GOAL" \
  --output none
echo "✅ ArmorCode configured"

# ============================================================
# STEP 3: Set Observability (Optional but Recommended)
# ============================================================

echo "Setting observability configuration..."
# Get these from Sentry.io and Slack
SENTRY_DSN="${SENTRY_DSN:-}"  # Leave empty if not configured
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"  # Leave empty if not configured

if [ -n "$SENTRY_DSN" ]; then
  az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEB_APP_NAME" \
    --settings SENTRY_DSN="$SENTRY_DSN" \
    --output none
  echo "✅ Sentry configured"
else
  echo "⚠️  SENTRY_DSN not set (optional)"
fi

if [ -n "$SLACK_WEBHOOK_URL" ]; then
  az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEB_APP_NAME" \
    --settings SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
    --output none
  echo "✅ Slack configured"
else
  echo "⚠️  SLACK_WEBHOOK_URL not set (optional)"
fi

# Clear sensitive variables from memory
unset ADO_PAT ARMORCODE_API_KEY API_PASSWORD MICROSOFT_APP_PASSWORD
unset SENTRY_DSN SLACK_WEBHOOK_URL EMAIL_PASSWORD

# ============================================================
# STEP 4: Configure Startup Command for FastAPI
# ============================================================

echo "Setting startup command for FastAPI..."
az webapp config set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEB_APP_NAME" \
  --startup-file "gunicorn -w 4 -k uvicorn.workers.UvicornWorker execution.api.app:app --bind 0.0.0.0:8000" \
  --output none
echo "✅ Startup command configured"

# ============================================================
# STEP 5: Verify Configuration
# ============================================================

echo ""
echo "============================================================"
echo "Configuration Complete!"
echo "============================================================"
echo ""
echo "✅ All credentials uploaded to Azure (encrypted)"
echo ""
echo "Verify settings at:"
echo "https://portal.azure.com → $WEB_APP_NAME → Configuration"
echo ""
echo "Test your API:"
echo "curl https://$WEB_APP_NAME.azurewebsites.net/health"
echo ""
echo "🔒 SECURITY REMINDERS:"
echo "   - .env file is NOT deployed (stays local only)"
echo "   - Credentials are encrypted in Azure Application Settings"
echo "   - Never commit .env to git (already in .gitignore)"
echo "   - Rotate credentials regularly"
echo ""
