# GitHub Actions Setup for DOE Weekly Report

This guide explains how to set up automated weekly DOE bug reports using GitHub Actions, so the report runs even when your laptop is off.

## Overview

GitHub Actions will run your DOE report automatically every Friday at 7:00 AM UTC on GitHub's servers. The workflow will:
1. Query Azure DevOps for bug data
2. Calculate weekly metrics
3. Send email report via Gmail SMTP
4. Save updated tracking data back to the repository

## Prerequisites

- GitHub repository (public or private)
- Azure DevOps access with Personal Access Token (PAT)
- Gmail account with App Password for SMTP

## Step 1: Push Your Code to GitHub

If you haven't already, initialize and push your repository:

```bash
git init
git add .
git commit -m "Initial commit with DOE tracking system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Step 2: Configure GitHub Secrets

GitHub Secrets store sensitive information like API keys and passwords securely. The workflow needs the following secrets:

### How to Add Secrets

1. Go to your GitHub repository
2. Click **Settings** (top menu)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Add each secret listed below

### Required Secrets

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `ADO_ORGANIZATION_URL` | Your Azure DevOps organization URL | `https://dev.azure.com/your-org` |
| `ADO_PROJECT_NAME` | Your ADO project name | `Your Project Name` |
| `ADO_PAT` | Azure DevOps Personal Access Token | `abcd1234...` |
| `EMAIL_ADDRESS` | Gmail address for sending reports | `your-email@gmail.com` |
| `EMAIL_PASSWORD` | Gmail App Password (NOT your regular password) | `abcd efgh ijkl mnop` |
| `SMTP_SERVER` | SMTP server address | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |

### How to Get Your Azure DevOps PAT

1. Go to https://dev.azure.com/YOUR_ORG
2. Click on **User Settings** (top right) → **Personal access tokens**
3. Click **+ New Token**
4. Configure:
   - **Name**: "GitHub Actions DOE Report"
   - **Organization**: Select your organization
   - **Expiration**: 90 days or custom
   - **Scopes**:
     - ✅ **Work Items** (Read)
5. Click **Create**
6. **IMPORTANT**: Copy the token immediately (you won't see it again)

### How to Get Your Gmail App Password

⚠️ **You CANNOT use your regular Gmail password**. You must create an App Password:

1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** if not already enabled
3. Go to https://myaccount.google.com/apppasswords
4. Click **Select app** → Choose **Mail**
5. Click **Select device** → Choose **Other** → Enter "GitHub Actions"
6. Click **Generate**
7. Copy the 16-character password (format: `abcd efgh ijkl mnop`)

## Step 3: Verify GitHub Actions Workflow

The workflow file is already created at [`.github/workflows/weekly-doe-report.yml`](.github/workflows/weekly-doe-report.yml).

### Schedule

The workflow runs:
- **Automatically**: Every Friday at 7:00 AM UTC
- **Manually**: Via GitHub UI (for testing)

### To Change the Schedule

Edit [`.github/workflows/weekly-doe-report.yml`](.github/workflows/weekly-doe-report.yml):

```yaml
schedule:
  - cron: '0 7 * * 5'  # Minute Hour DayOfMonth Month DayOfWeek
```

**Cron examples:**
- `'0 7 * * 5'` - 7 AM UTC every Friday
- `'0 12 * * 5'` - 12 PM UTC every Friday (7 AM EST)
- `'0 15 * * 1'` - 3 PM UTC every Monday

**UTC to your timezone:**
- EST (UTC-5): 7 AM UTC = 2 AM EST
- PST (UTC-8): 7 AM UTC = 11 PM PST (previous day)
- GMT (UTC+0): 7 AM UTC = 7 AM GMT

## Step 4: Test the Workflow

### Manual Test Run

1. Go to your GitHub repository
2. Click **Actions** (top menu)
3. Click **DOE Weekly Bug Report** (left sidebar)
4. Click **Run workflow** button (right side)
5. Click **Run workflow** (green button)
6. Wait for the workflow to complete (~2-3 minutes)

### Check Results

- ✅ **Green checkmark** = Success
- ❌ **Red X** = Failed (click to see error logs)

### View Logs

1. Click on the workflow run
2. Click on **send-report** job
3. Expand each step to see detailed logs
4. Download artifacts (logs) at the bottom of the page

## Step 5: Verify Email Delivery

After a successful run:
1. Check your inbox (recipient configured in `send_doe_report.py`)
2. Look for email with subject: "Bug Position - ALCM - Week X"
3. Email should have HTML formatting with status colors

## Troubleshooting

### Workflow Fails with "Baseline not found"

**Problem**: Data files missing from repository

**Solution**:
```bash
# Ensure data files are committed
git add data/baseline.json data/weekly_tracking.json
git commit -m "Add baseline and tracking data"
git push
```

### Workflow Fails with "Authentication failed"

**Problem**: Invalid ADO PAT or Gmail password

**Solutions**:
1. **Azure DevOps PAT expired**
   - Generate a new PAT
   - Update the `ADO_PAT` secret in GitHub

2. **Gmail authentication failed**
   - Verify you're using an **App Password**, not regular password
   - Regenerate App Password if needed
   - Update the `EMAIL_PASSWORD` secret in GitHub

### Workflow Fails with "Connection refused"

**Problem**: SMTP server or port incorrect

**Solution**:
- Verify `SMTP_SERVER` = `smtp.gmail.com`
- Verify `SMTP_PORT` = `587`

### Email Not Received

**Possible causes**:
1. Check spam/junk folder
2. Verify recipient email in [`send_doe_report.py`](execution/send_doe_report.py) line 41
3. Check Gmail "Sent" folder to confirm email was sent
4. Review workflow logs for email sending step

### Workflow Doesn't Run on Schedule

**Possible causes**:
1. **Repository is private**: Scheduled workflows may have delays on free plans
2. **Cron timezone**: GitHub Actions uses UTC timezone
3. **First run**: May take up to 1 hour after pushing workflow file

**Solutions**:
- Test with manual trigger first
- Ensure workflow file is on `main` branch
- Check Actions tab for any errors

## Data Persistence

The workflow automatically saves updated tracking data:

1. **Before run**: Copies `data/baseline.json` and `data/weekly_tracking.json` to `.tmp/`
2. **During run**: Scripts read/write to `.tmp/`
3. **After run**: Copies updated `data/weekly_tracking.json` back and commits to repo

This ensures your weekly tracking data persists between runs.

## Cost

**GitHub Actions is FREE for:**
- Public repositories (unlimited)
- Private repositories (2,000 minutes/month)

**This workflow uses:**
- ~3 minutes per run
- ~12 minutes per month (4 Fridays)
- Well within free tier limits

## Monitoring

### Enable Email Notifications

Get notified when workflows fail:

1. GitHub → Settings → Notifications
2. Scroll to **GitHub Actions**
3. Enable **Send notifications for failed workflows**

### View Workflow History

- Go to **Actions** tab
- See all past runs with status indicators
- Download logs for any run (kept for 90 days)

## Security Best Practices

1. ✅ **Never commit secrets** - Use GitHub Secrets only
2. ✅ **Rotate credentials** - Update PAT and App Password every 90 days
3. ✅ **Limit PAT scope** - Only grant "Work Items: Read" permission
4. ✅ **Use App Passwords** - Never use your main Gmail password
5. ✅ **Review workflow logs** - Check for any exposed sensitive data

## Switching Back to Local Scheduling

If you want to disable GitHub Actions and use local Windows Task Scheduler:

1. Go to repository → Settings → Actions → General
2. Under "Actions permissions", select **Disable actions**
3. Or delete [`.github/workflows/weekly-doe-report.yml`](.github/workflows/weekly-doe-report.yml)

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cron Expression Generator](https://crontab.guru/)
- [Gmail App Passwords Guide](https://support.google.com/accounts/answer/185833)
- [Azure DevOps PAT Documentation](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate)

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review workflow logs in the Actions tab
3. Verify all secrets are correctly configured
4. Test scripts locally first to isolate the issue

---

**✅ Setup Complete!**

Your DOE weekly report will now run automatically every Friday at 7 AM UTC, even when your laptop is off.
