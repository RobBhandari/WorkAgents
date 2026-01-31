# ArmorCode Weekly Report - GitHub Actions Setup

This document explains how to configure GitHub secrets for the ArmorCode weekly security report workflow.

## Workflow Schedule

The workflow runs automatically every **Friday at 7:00 AM UTC** and sends a security report email to configured recipients.

You can also trigger it manually from the GitHub Actions tab using the "Run workflow" button.

## Required GitHub Secrets

Navigate to your repository settings: **Settings → Secrets and variables → Actions → New repository secret**

### ArmorCode Configuration

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `ARMORCODE_API_KEY` | `e12138f9-1e65-46cf-86f0-7ee8f8ce142a` | ArmorCode API key from Settings → API Keys |
| `ARMORCODE_BASE_URL` | `https://app.armorcode.com` | ArmorCode instance URL |
| `ARMORCODE_PRODUCTS` | `Access Diversity,Access Legal AI Services,Access Legal Case Management,Access Legal Compliance,Access Legal Framework,Access MyCalendars,Eclipse,Law Fusion,Legal Bricks,Legal Workspace,One Office & Financial Director,Proclaim,Proclaim Portals - Eclipse,inCase` | Comma-separated list of products to track |
| `ARMORCODE_EMAIL_RECIPIENTS` | `robin.bhandari@theaccessgroup.com` | Email addresses to receive reports (comma-separated) |
| `ARMORCODE_BASELINE_DATE` | `2025-12-01` | Reference date for baseline (informational) |
| `ARMORCODE_TARGET_DATE` | `2026-06-30` | Target date for 70% reduction goal |
| `ARMORCODE_REDUCTION_GOAL` | `0.70` | Reduction goal as decimal (0.70 = 70%) |

### Email Configuration (SMTP)

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `EMAIL_ADDRESS` | `robin.bhandari.76@gmail.com` | Sender email address |
| `EMAIL_PASSWORD` | `rcjq tbbx cybf mjak` | Gmail App Password (not account password) |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server address |
| `SMTP_PORT` | `587` | SMTP port (usually 587 for TLS) |

## Gmail App Password Setup

For Gmail accounts, you need to use an App Password, not your regular account password:

1. Go to https://myaccount.google.com/apppasswords
2. Sign in to your Google account
3. Generate a new app password for "Mail"
4. Use this 16-character password as `EMAIL_PASSWORD`

## Workflow Files

- **Workflow**: [`.github/workflows/armorcode-weekly-report.yml`](armorcode-weekly-report.yml)
- **Scripts**:
  - `execution/armorcode_weekly_query.py` - Query current vulnerabilities
  - `execution/armorcode_generate_report.py` - Generate HTML report
  - `execution/armorcode_send_email.py` - Send email

## Baseline File

The baseline snapshot is stored in `data/armorcode_baseline.json` and represents the starting point (281 vulnerabilities as of Jan 31, 2026). This file is static and should not change unless manually regenerated.

## Manual Testing

To test the workflow manually:

1. Go to **Actions** tab in GitHub
2. Select **ArmorCode Weekly Security Report**
3. Click **Run workflow**
4. Select branch and click **Run workflow**

## Artifacts

Each workflow run stores artifacts for 90 days:
- Weekly query results (JSON)
- HTML report
- Log files

Access artifacts from the Actions run page.
