# Azure Web App Deployment Guide

Complete guide for deploying the Engineering Metrics API to Azure Web App.

---

## 📋 Pre-Deployment Checklist

Before deploying, ensure you have:

- ✅ Azure subscription with permissions to create resources
- ✅ Azure CLI installed (`az --version`)
- ✅ Local `.env` file configured and working
- ✅ All tests passing locally (`pytest tests/`)
- ✅ API running locally (`uvicorn execution.api.app:app`)

---

## 🚀 Deployment Steps

### Step 1: Create Azure Resources

```bash
# Login to Azure
az login

# Set your subscription (if you have multiple)
az account set --subscription "Your Subscription Name"

# Create resource group
az group create \
  --name metrics-api-rg \
  --location eastus

# Create App Service Plan (Basic B1 tier recommended for production)
az appservice plan create \
  --name metrics-api-plan \
  --resource-group metrics-api-rg \
  --sku B1 \
  --is-linux

# Create Web App (Python 3.11)
az webapp create \
  --name metrics-api-prod \
  --resource-group metrics-api-rg \
  --plan metrics-api-plan \
  --runtime "PYTHON:3.11"
```

---

### Step 2: Configure Application Settings

**Option A: Use the automated script** ⭐ (Recommended)

```bash
# 1. Edit deploy-azure-config.sh and update:
#    - RESOURCE_GROUP (line 8)
#    - WEB_APP_NAME (line 9)
#    - API_PASSWORD (line 17) - CHANGE FROM DEFAULT!

# 2. Make script executable
chmod +x deploy-azure-config.sh

# 3. Run the script (it reads from your .env file)
./deploy-azure-config.sh
```

**Option B: Manual configuration in Azure Portal**

```
1. Navigate to: Azure Portal → metrics-api-prod → Configuration
2. Click "+ New application setting" for each:

   API_USERNAME = metrics_admin
   API_PASSWORD = [strong password, min 8 chars]

   ADO_ORGANIZATION_URL = https://dev.azure.com/your-org
   ADO_PROJECT_NAME = Your Project
   ADO_PAT = [your PAT token]

   ARMORCODE_API_KEY = [your API key]
   ARMORCODE_BASE_URL = https://app.armorcode.com
   ARMORCODE_ENVIRONMENT = PRODUCTION
   ARMORCODE_PRODUCTS = Product1,Product2,...

   SENTRY_DSN = [optional, for error tracking]
   SLACK_WEBHOOK_URL = [optional, for alerts]

3. Click "Save" at the top
```

---

### Step 3: Configure Startup Command

Azure needs to know how to start your FastAPI app.

```bash
az webapp config set \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --startup-file "gunicorn -w 4 -k uvicorn.workers.UvicornWorker execution.api.app:app --bind 0.0.0.0:8000"
```

**What this does**:
- Runs Gunicorn with 4 worker processes
- Uses Uvicorn workers (required for FastAPI async)
- Binds to port 8000 (Azure's default)

---

### Step 4: Add Gunicorn to Requirements

```bash
# Add to requirements.txt
echo "gunicorn>=21.0.0" >> requirements.txt

# Commit the change
git add requirements.txt
git commit -m "Add gunicorn for Azure deployment"
```

---

### Step 5: Deploy Code

**Option A: Deploy from Local Git** (Simple)

```bash
# Configure local Git deployment
az webapp deployment source config-local-git \
  --name metrics-api-prod \
  --resource-group metrics-api-rg

# Get the Git URL
GIT_URL=$(az webapp deployment source config-local-git \
  --name metrics-api-prod \
  --resource-group metrics-api-rg \
  --query url -o tsv)

# Add Azure as a remote
git remote add azure $GIT_URL

# Deploy
git push azure main
```

**Option B: Deploy from GitHub Actions** (Automated)

```yaml
# .github/workflows/deploy-azure.yml
name: Deploy to Azure Web App

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Deploy to Azure Web App
        uses: azure/webapps-deploy@v2
        with:
          app-name: metrics-api-prod
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

---

### Step 6: Verify Deployment

```bash
# 1. Check health endpoint
curl https://metrics-api-prod.azurewebsites.net/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2026-02-08T...",
  "data_freshness": {...}
}

# 2. Test authentication
curl https://metrics-api-prod.azurewebsites.net/api/v1/metrics/quality/latest \
  -u metrics_admin:your_password

# 3. Check logs
az webapp log tail \
  --resource-group metrics-api-rg \
  --name metrics-api-prod
```

---

## 🔍 Troubleshooting

### Issue: App not starting

**Check logs**:
```bash
az webapp log tail --resource-group metrics-api-rg --name metrics-api-prod
```

**Common causes**:
- Missing `gunicorn` in requirements.txt
- Wrong startup command
- Missing required environment variables

### Issue: 500 Internal Server Error

**Check application logs**:
```bash
# Enable application logging
az webapp log config \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --application-logging filesystem

# View logs
az webapp log tail --resource-group metrics-api-rg --name metrics-api-prod
```

**Common causes**:
- Missing environment variables (ADO_PAT, ARMORCODE_API_KEY)
- Invalid configuration (check secure_config.py validation)

### Issue: Authentication not working

**Verify Application Settings**:
```bash
# List all settings (API_USERNAME and API_PASSWORD should be present)
az webapp config appsettings list \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --query "[?name=='API_USERNAME' || name=='API_PASSWORD']"
```

---

## 🔒 Security Checklist

Before going to production:

- [ ] Changed API_PASSWORD from default value
- [ ] API_USERNAME is not "admin" or other common name
- [ ] All sensitive values in Application Settings (not in code)
- [ ] HTTPS enabled (default in Azure)
- [ ] Rate limiting configured (already in middleware)
- [ ] Sentry configured for error tracking
- [ ] Slack webhook configured for alerts

---

## 📊 Post-Deployment Tasks

### 1. Set Up Monitoring

**Enable Application Insights**:
```bash
az monitor app-insights component create \
  --app metrics-api-insights \
  --resource-group metrics-api-rg \
  --location eastus \
  --application-type web

# Link to Web App
az webapp config appsettings set \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="[connection string from above]"
```

### 2. Configure Automated Backups

```bash
# Create storage account for backups
az storage account create \
  --name metricsapibackup \
  --resource-group metrics-api-rg \
  --location eastus \
  --sku Standard_LRS

# Enable automatic backups (requires Standard tier or higher)
# Note: Upgrade App Service Plan if using Basic tier
```

### 3. Set Up Deployment Slots (Staging)

```bash
# Create staging slot
az webapp deployment slot create \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --slot staging

# Deploy to staging first, then swap to production
az webapp deployment slot swap \
  --resource-group metrics-api-rg \
  --name metrics-api-prod \
  --slot staging
```

---

## 🎯 Production Readiness Summary

| Item | Status | Action |
|------|--------|--------|
| Azure Resources | ⚠️ To Do | Create resource group, plan, web app |
| Application Settings | ⚠️ To Do | Configure API credentials + integrations |
| Startup Command | ⚠️ To Do | Set Gunicorn command |
| Gunicorn Dependency | ⚠️ To Do | Add to requirements.txt |
| Code Deployment | ⚠️ To Do | Git push or GitHub Actions |
| Health Check | ⚠️ To Do | Verify /health endpoint |
| API Authentication | ⚠️ To Do | Test with credentials |
| Sentry/Slack | ⚠️ Optional | Configure observability |
| Application Insights | ⚠️ Optional | Set up Azure monitoring |

---

## 📞 Support

**Azure Resources**:
- [App Service Python docs](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [Deploy Python to Azure](https://learn.microsoft.com/en-us/azure/developer/python/tutorial-deploy-app-service-on-linux)

**Project Resources**:
- [README.md](README.md) - Project overview
- [API Documentation](http://localhost:8000/docs) - After starting locally

---

**Next Steps**: Run `./deploy-azure-config.sh` after creating your Azure Web App!
