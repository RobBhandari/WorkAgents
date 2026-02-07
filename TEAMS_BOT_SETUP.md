# Microsoft Teams Bug Position Bot - Complete Setup Guide

This guide will walk you through setting up a personal Teams bot that provides instant bug position reports, available 24/7.

**Time Required:** 30-45 minutes
**Cost:** Free (using Azure Free tier)
**Privacy:** Personal bot - only you can see/use it

---

## 📋 Prerequisites

- Microsoft Teams account (work account)
- Azure subscription (work account - likely already have access)
- Admin access to your computer (for installing dependencies)

---

## Part 1: Install Dependencies (5 minutes)

### Step 1: Install Bot Framework SDK

Open Command Prompt or PowerShell:

```bash
cd c:\DEV\Agentic-Test
.venv\Scripts\python.exe -m pip install botbuilder-core==4.15.0 aiohttp==3.9.1
```

✅ **Checkpoint:** You should see "Successfully installed botbuilder-core aiohttp"

---

## Part 2: Create Azure Bot Service (15 minutes)

### Step 1: Open Azure Portal

1. Go to: https://portal.azure.com
2. Sign in with your work account

### Step 2: Create a Resource Group

1. Click **"Create a resource"**
2. Search for **"Resource Group"**
3. Click **"Create"**
4. Fill in:
   - **Subscription:** (your work subscription)
   - **Resource group:** `bug-position-bot-rg`
   - **Region:** `UK South` (or your preferred region)
5. Click **"Review + create"** → **"Create"**

### Step 3: Create Azure Bot

1. In Azure Portal, click **"Create a resource"**
2. Search for **"Azure Bot"**
3. Click **"Create"**
4. Fill in:
   - **Bot handle:** `bug-position-bot-{your-initials}` (e.g., `bug-position-bot-rb`)
   - **Subscription:** (your work subscription)
   - **Resource group:** `bug-position-bot-rg` (select existing)
   - **Pricing tier:** **F0 (Free)** - 10,000 messages/month
   - **Microsoft App ID:** Select **"Create new Microsoft App ID"**
   - **App type:** **"Multi Tenant"**
5. Click **"Review + create"** → **"Create"**
6. Wait for deployment to complete (~2 minutes)

### Step 4: Get Bot Credentials

1. Go to your bot resource (click **"Go to resource"** after deployment)
2. Click **"Configuration"** in the left menu
3. You'll see:
   - **Microsoft App ID:** (copy this - looks like `12345678-1234-1234-1234-123456789abc`)
4. Click **"Manage"** next to Microsoft App ID
5. Click **"Certificates & secrets"** → **"Client secrets"** → **"New client secret"**
6. Description: `bug-bot-secret`
7. Expires: `24 months`
8. Click **"Add"**
9. **IMMEDIATELY COPY THE SECRET VALUE** (you won't see it again!)

### Step 5: Update .env File

1. Open: `c:\DEV\Agentic-Test\.env`
2. Find these lines:
   ```
   MICROSOFT_APP_ID=your_microsoft_app_id_here
   MICROSOFT_APP_PASSWORD=your_microsoft_app_password_here
   ```
3. Replace with your actual values:
   ```
   MICROSOFT_APP_ID=12345678-1234-1234-1234-123456789abc
   MICROSOFT_APP_PASSWORD=your_secret_value_here
   ```
4. Save the file

✅ **Checkpoint:** Your .env file now has bot credentials

---

## Part 3: Deploy to Azure App Service (15 minutes)

### Step 1: Create App Service Plan

1. In Azure Portal, click **"Create a resource"**
2. Search for **"App Service Plan"**
3. Click **"Create"**
4. Fill in:
   - **Subscription:** (your work subscription)
   - **Resource group:** `bug-position-bot-rg`
   - **Name:** `bug-bot-plan`
   - **Operating System:** **Linux**
   - **Region:** `UK South`
   - **Pricing Tier:** Click **"Explore pricing plans"** → Select **"Free F1"** (free forever)
5. Click **"Review + create"** → **"Create"**

### Step 2: Create Web App

1. In Azure Portal, click **"Create a resource"**
2. Search for **"Web App"**
3. Click **"Create"**
4. Fill in:
   - **Subscription:** (your work subscription)
   - **Resource group:** `bug-position-bot-rg`
   - **Name:** `bug-position-bot-{your-initials}` (must be globally unique)
   - **Publish:** **Code**
   - **Runtime stack:** **Python 3.11**
   - **Operating System:** **Linux**
   - **Region:** `UK South`
   - **App Service Plan:** `bug-bot-plan` (select existing)
5. Click **"Review + create"** → **"Create"**
6. Wait for deployment (~2 minutes)

### Step 3: Configure Environment Variables in Azure

1. Go to your Web App resource
2. Click **"Configuration"** in the left menu under Settings
3. Click **"+ New application setting"** and add each of these:

| Name | Value (from your .env file) |
|------|------------------------------|
| `ADO_ORGANIZATION_URL` | https://dev.azure.com/access-devops |
| `ADO_PROJECT_NAME` | Access Legal Case Management |
| `ADO_PAT` | (your Azure DevOps PAT) |
| `MICROSOFT_APP_ID` | (your bot app ID) |
| `MICROSOFT_APP_PASSWORD` | (your bot secret) |

4. Click **"Save"** at the top
5. Click **"Continue"** when prompted to restart

### Step 4: Deploy Code to Azure

**Option A: Deploy via VS Code (Easiest)**

1. Install "Azure App Service" extension in VS Code
2. Click Azure icon in sidebar
3. Find your Web App under subscriptions
4. Right-click → **"Deploy to Web App"**
5. Select `c:\DEV\Agentic-Test` folder
6. Confirm deployment

**Option B: Deploy via Azure CLI**

```bash
# Install Azure CLI if needed
# https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows

# Login to Azure
az login

# Deploy
cd c:\DEV\Agentic-Test
az webapp up --name bug-position-bot-{your-initials} --resource-group bug-position-bot-rg
```

**Option C: Deploy via ZIP file (Manual)**

1. Create ZIP of your project (exclude .venv, .git, .tmp)
2. In Azure Portal, go to your Web App
3. Click **"Deployment Center"** → **"FTPS credentials"**
4. Use FTP client to upload ZIP
5. In Kudu console (`{your-app}.scm.azurewebsites.net`), unzip

✅ **Checkpoint:** Your bot is deployed and running!

### Step 5: Configure Bot Endpoint

1. Go back to your **Azure Bot** resource (not Web App)
2. Click **"Configuration"**
3. Set **Messaging endpoint:** `https://bug-position-bot-{your-initials}.azurewebsites.net/api/messages`
4. Click **"Apply"**

✅ **Checkpoint:** Bot endpoint is configured

---

## Part 4: Add Bot to Microsoft Teams (5 minutes)

### Step 1: Enable Teams Channel

1. In your **Azure Bot** resource
2. Click **"Channels"** in the left menu
3. Click the **Microsoft Teams** icon
4. Click **"Save"**
5. Accept terms of service
6. Teams channel is now enabled!

### Step 2: Install Bot in Your Teams

1. Still in Channels, click **"Microsoft Teams"** (the text link)
2. This opens Teams in your browser/app
3. A dialog appears: **"Bug Position Bot wants to..."**
4. Click **"Add"**

✅ **Checkpoint:** Bot appears in your Teams chat list!

---

## Part 5: Test Your Bot! (5 minutes)

### Step 1: Open Chat with Bot

1. In Microsoft Teams, find **"Bug Position Bot"** in your chat list
2. Open the chat

### Step 2: Try Commands

Send these messages to test:

```
help
```

You should get a welcome message with available commands!

```
bugposition
```

You should get the full multi-project bug position report!

```
week
```

You should get the current week number!

```
projects
```

You should get a list of all tracked projects!

---

## 🎉 Success! Your Bot is Live!

You can now:
- ✅ Query bug position from Teams anytime
- ✅ Works on desktop, mobile, web
- ✅ Bot runs 24/7 (even when your laptop is off)
- ✅ Only you can see/use it (private)

---

## 💬 Available Commands

| Command | Description |
|---------|-------------|
| `help` | Show available commands |
| `bugposition` | Full multi-project bug report |
| `week` | Current week number |
| `projects` | List all tracked projects |
| `project <name>` | Details for specific project |

---

## 🔧 Troubleshooting

### Bot doesn't respond

**Check:**
1. Is Web App running? (Azure Portal → Web App → Overview)
2. Check logs: Azure Portal → Web App → Log stream
3. Verify endpoint: Azure Bot → Configuration → Messaging endpoint

### "No projects found" error

**Fix:**
1. Make sure you've run `ado_doe_tracker.py` locally first
2. Tracking files (`baseline_*.json`, `weekly_tracking_*.json`) need to exist
3. For now, bot reads local files - we'll sync these to Azure next

### Bot shows up but gives errors

**Check logs:**
1. Azure Portal → Web App → Log stream
2. Look for Python errors
3. Verify all environment variables are set in Configuration

---

## 🚀 Next Steps (Optional)

### Make Bot Read Live Data

Currently bot reads `.tmp/*.json` files. To make it query Azure DevOps directly:

1. Update bot code to call `load_all_projects()` which queries ADO
2. Or set up automated sync of tracking files to Azure storage

### Share Bot with Colleagues

1. Azure Bot → Channels → Microsoft Teams
2. Get install link
3. Share with specific people
4. They can add bot to their Teams

### Add to Team Channel

1. In Teams, go to a team channel
2. Click **"+"** → **"More apps"**
3. Search for your bot name
4. Add to channel
5. Team members can query it

---

## 💰 Cost Breakdown

**Total Cost: FREE**

- Azure Bot (F0): Free - 10,000 messages/month
- App Service Plan (F1): Free forever
- Web App: Free (uses F1 plan)
- Storage: Minimal (covered by free tier)

**Monthly estimate: £0.00**

---

## 🗑️ How to Delete Everything

If you want to remove the bot:

1. Azure Portal → Resource Groups
2. Find `bug-position-bot-rg`
3. Click **"Delete resource group"**
4. Type the name to confirm
5. Click **"Delete"**

Everything is removed (bot, web app, plan, all resources).

---

## ❓ Need Help?

**Common Issues:**

1. **Bot not responding:** Check Web App logs in Azure Portal
2. **Authentication errors:** Verify MICROSOFT_APP_ID and MICROSOFT_APP_PASSWORD
3. **"No projects" error:** Run ado_doe_tracker.py locally first

---

**Created:** 2026-01-30
**Author:** Claude Code
**Status:** Ready to deploy!
