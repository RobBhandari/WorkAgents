# GitHub Actions - Dashboard Automation

## Overview

The `refresh-dashboards.yml` workflow automatically refreshes all Observatory dashboards on a schedule, ensuring data is always up-to-date without requiring a local machine to be running.

## Workflow Details

- **Schedule**: Runs daily at 6 AM UTC
- **Manual Trigger**: Can be triggered manually from GitHub Actions UI
- **Platform**: Runs on GitHub's Ubuntu runners (cloud-based)

## Required GitHub Secrets

Before the workflow can run, you must configure these secrets in your GitHub repository:

### Setting Up Secrets

1. Go to your GitHub repository
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"** and add each of the following:

### Required Secrets

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `AZURE_DEVOPS_ORG_URL` | Azure DevOps organization URL | `https://dev.azure.com/your-org` |
| `AZURE_DEVOPS_PAT` | Personal Access Token for ADO | `your-pat-token-here` |
| `ARMORCODE_API_URL` | ArmorCode API endpoint | `https://your-org.armorcode.ai/api/graphql` |
| `ARMORCODE_API_KEY` | ArmorCode API key | `your-api-key-here` |

### How to Get These Values

#### Azure DevOps PAT Token
1. Go to Azure DevOps → User Settings → Personal Access Tokens
2. Create new token with these scopes:
   - **Work Items**: Read
   - **Code**: Read
   - **Project and Team**: Read
3. Copy the token (you won't see it again!)

#### ArmorCode API Key
1. Log into ArmorCode
2. Go to Settings → API Keys
3. Generate new API key
4. Copy the key and API endpoint URL

## What the Workflow Does

1. **Checks out** the repository
2. **Sets up Python** 3.11 with pip caching
3. **Installs dependencies** from requirements.txt
4. **Sets environment variables** from GitHub secrets (secure, no file creation)
5. **Collects metrics** from:
   - Azure DevOps (Quality, Flow, Ownership, Risk)
   - ArmorCode (Security)
6. **Generates dashboards** (HTML files)
7. **Commits and pushes** updated dashboards back to repo

## Manual Trigger

To manually trigger the workflow:

1. Go to your GitHub repository
2. Navigate to: **Actions** → **Refresh Observatory Dashboards**
3. Click **"Run workflow"** button
4. Select branch and click **"Run workflow"**

## Monitoring Workflow Runs

View workflow execution history:
- Go to **Actions** tab in your repository
- Click on **"Refresh Observatory Dashboards"**
- View logs for each run

## Local Refresh (Alternative)

If you want to refresh dashboards locally instead:

```bash
# Run all collectors and generators (uses local .env file for credentials)
py execution/refresh_all_dashboards.py
```

**Note**: Local development uses `.env` file (gitignored) for credentials, while CI/CD uses environment variables directly from GitHub Secrets. Both methods work identically since the code reads from `os.getenv()`.

## Troubleshooting

### Workflow Fails with Authentication Error
- Verify GitHub secrets are set correctly
- Check if Azure DevOps PAT token has expired
- Ensure PAT token has required permissions

### Workflow Fails on Specific Dashboard
- The workflow uses `continue-on-error: true` for each step
- If one dashboard fails, others will still run
- Check workflow logs to see specific error messages

### Dashboards Not Updating
- Check if workflow is enabled (Actions tab)
- Verify schedule cron expression
- Check if repository has Actions enabled in Settings

## Adjusting Schedule

To change the refresh frequency, edit the cron schedule in `.github/workflows/refresh-dashboards.yml`:

```yaml
schedule:
  - cron: '0 6 * * *'  # Daily at 6 AM UTC
```

Common schedules:
- `0 */6 * * *` - Every 6 hours
- `0 0 * * *` - Daily at midnight UTC
- `0 9 * * 1-5` - Weekdays at 9 AM UTC
- `0 6,18 * * *` - Twice daily at 6 AM and 6 PM UTC

## Cost Considerations

- GitHub Actions provides **2,000 free minutes/month** for private repos
- This workflow takes ~5-10 minutes per run
- Daily runs = ~300 minutes/month (well within free tier)
- Public repos have unlimited free minutes
