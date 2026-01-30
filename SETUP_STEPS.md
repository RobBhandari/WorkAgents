# Step-by-Step Setup Guide

Follow these steps **in order** to get your DOE weekly report running automatically on GitHub Actions.

---

## ✅ STEP 1: Commit Your Files to Git

Open your terminal in `c:\DEV\Agentic-Test` and run these commands:

```bash
# Add all files to git
git add .

# Create your first commit
git commit -m "Add DOE weekly report with GitHub Actions workflow"

# Rename branch to 'main' (GitHub's default)
git branch -M main
```

**Expected output:**
```
[main (root-commit) abc1234] Add DOE weekly report with GitHub Actions workflow
 XX files changed, XXX insertions(+)
```

---

## ✅ STEP 2: Create a GitHub Repository

### Option A: Using GitHub Website (Easiest)

1. Go to https://github.com/new
2. Fill in the form:
   - **Repository name**: `Agentic-Test` (or any name you prefer)
   - **Description**: "DOE bug tracking with automated weekly reports"
   - **Visibility**: Choose **Private** (recommended) or Public
   - ⚠️ **DO NOT** check "Add a README file"
   - ⚠️ **DO NOT** check "Add .gitignore"
   - ⚠️ **DO NOT** choose a license
3. Click **Create repository**

### Option B: Using GitHub CLI (If you have `gh` installed)

```bash
gh repo create Agentic-Test --private --source=. --remote=origin --push
```

If you used Option B, **skip to STEP 4** (GitHub CLI does STEP 3 automatically).

---

## ✅ STEP 3: Connect Your Local Repo to GitHub

After creating the repository on GitHub, you'll see a page with instructions. Run these commands:

```bash
# Add GitHub as remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/Agentic-Test.git

# Push your code to GitHub
git push -u origin main
```

**Example with actual username:**
```bash
git remote add origin https://github.com/robinbhandari/Agentic-Test.git
git push -u origin main
```

**Expected output:**
```
Enumerating objects: XX, done.
Counting objects: 100% (XX/XX), done.
...
To https://github.com/YOUR_USERNAME/Agentic-Test.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

If prompted for credentials:
- **Username**: Your GitHub username
- **Password**: Use a **Personal Access Token** (not your GitHub password)
  - Create one here: https://github.com/settings/tokens
  - Scopes needed: `repo` (full control)

---

## ✅ STEP 4: Add GitHub Secrets

Now we need to add your API keys and passwords securely.

1. **Go to your repository on GitHub**
   - URL: `https://github.com/YOUR_USERNAME/Agentic-Test`

2. **Click "Settings"** (top menu bar)

3. **In the left sidebar:**
   - Click **"Secrets and variables"**
   - Click **"Actions"**

4. **Click "New repository secret"** (green button)

5. **Add each secret below** (one at a time):

### Secret 1: ADO_ORGANIZATION_URL
- **Name**: `ADO_ORGANIZATION_URL`
- **Value**: `https://dev.azure.com/access-devops`
- Click **Add secret**

### Secret 2: ADO_PROJECT_NAME
- Click **New repository secret** again
- **Name**: `ADO_PROJECT_NAME`
- **Value**: `Access Legal Case Management`
- Click **Add secret**

### Secret 3: ADO_PAT
- Click **New repository secret** again
- **Name**: `ADO_PAT`
- **Value**: `4HnazriRF0JEHtmnbnjCgB87N61mpcwh5uPPQXSLauh4k4uyt7LlJQQJ99CAACAAAAAFWvOZAAASAZDO1tJ9`
  - ⚠️ **IMPORTANT**: This is from your `.env` file
  - ⚠️ If this PAT is expired, create a new one at: https://dev.azure.com/access-devops/_usersSettings/tokens
- Click **Add secret**

### Secret 4: EMAIL_ADDRESS
- Click **New repository secret** again
- **Name**: `EMAIL_ADDRESS`
- **Value**: `robin.bhandari.76@gmail.com`
- Click **Add secret**

### Secret 5: EMAIL_PASSWORD
- Click **New repository secret** again
- **Name**: `EMAIL_PASSWORD`
- **Value**: `rcjq tbbx cybf mjak`
  - ⚠️ **IMPORTANT**: This is your Gmail App Password from `.env`
  - ⚠️ If this doesn't work, create a new App Password at: https://myaccount.google.com/apppasswords
- Click **Add secret**

### Secret 6: SMTP_SERVER
- Click **New repository secret** again
- **Name**: `SMTP_SERVER`
- **Value**: `smtp.gmail.com`
- Click **Add secret**

### Secret 7: SMTP_PORT
- Click **New repository secret** again
- **Name**: `SMTP_PORT`
- **Value**: `587`
- Click **Add secret**

**After adding all 7 secrets, you should see:**
```
✓ ADO_ORGANIZATION_URL
✓ ADO_PAT
✓ ADO_PROJECT_NAME
✓ EMAIL_ADDRESS
✓ EMAIL_PASSWORD
✓ SMTP_PORT
✓ SMTP_SERVER
```

---

## ✅ STEP 5: Test the Workflow

Now let's test if everything works!

1. **Go to the Actions tab**
   - In your GitHub repository, click **"Actions"** (top menu)

2. **Find your workflow**
   - In the left sidebar, click **"DOE Weekly Bug Report"**

3. **Run the workflow manually**
   - Click **"Run workflow"** button (right side, gray button)
   - Keep "Branch: main" selected
   - Click **"Run workflow"** (green button)

4. **Watch it run**
   - You'll see a new workflow run appear (yellow dot = running)
   - Click on it to see real-time progress
   - Takes about 2-3 minutes

5. **Check the results**
   - ✅ **Green checkmark** = SUCCESS!
   - ❌ **Red X** = Failed (click on it to see error logs)

---

## ✅ STEP 6: Verify Email Was Sent

After the workflow completes successfully:

1. **Check your email inbox**
   - Look for: `robin.bhandari@theaccessgroup.com`
   - Subject: "Bug Position - ALCM - Week X"

2. **Email should have:**
   - HTML formatting with colored status boxes
   - Current bug counts
   - Weekly activity (closed, created, net burn)
   - Timeline remaining

3. **If you don't see it:**
   - Check spam/junk folder
   - Check the workflow logs for errors
   - Verify the recipient email in `execution/send_doe_report.py` line 41

---

## ✅ STEP 7: Verify Automatic Scheduling

Your workflow is now scheduled to run **every Friday at 7:00 AM UTC** automatically.

### Check the schedule:
1. Go to **Actions** tab
2. Click **"DOE Weekly Bug Report"**
3. You'll see the schedule at the top: `On schedule`

### Next automatic run:
- **Every Friday at 7:00 AM UTC**
- This is approximately:
  - **2:00 AM EST** (7 AM UTC - 5 hours)
  - **7:00 AM GMT** (same as UTC)

### To change the time:
1. Edit `.github/workflows/weekly-doe-report.yml`
2. Change line 6: `- cron: '0 7 * * 5'`
   - Format: `'minute hour * * dayOfWeek'`
   - Example for 12 PM UTC: `'0 12 * * 5'`
3. Commit and push the change

---

## 🎉 YOU'RE DONE!

### What happens now:

✅ Every Friday at 7 AM UTC:
1. GitHub Actions wakes up
2. Queries Azure DevOps for bug data
3. Calculates weekly metrics
4. Sends HTML email report
5. Saves updated tracking data back to repo
6. Goes back to sleep

✅ **Even if your laptop is:**
- Powered off
- Asleep
- Disconnected from internet
- On vacation with you

### Monitoring:

- **View past runs**: GitHub → Actions tab
- **Download logs**: Click any run → Scroll down → Download artifacts
- **Get notifications**: GitHub → Settings → Notifications → Enable "Failed workflows"

---

## 🆘 Troubleshooting

### Workflow Failed?

**Check the error message:**
1. Click on the failed run
2. Click on "send-report" job
3. Expand the failed step (red X)
4. Read the error message

**Common issues:**

| Error Message | Solution |
|--------------|----------|
| "Baseline not found" | Make sure `data/baseline.json` exists in repo |
| "Authentication failed" | Check your ADO_PAT or EMAIL_PASSWORD secrets |
| "Connection refused" | Verify SMTP_SERVER and SMTP_PORT secrets |
| "Access denied" | Check if your ADO PAT has expired |

### Need to update secrets?

1. Go to Settings → Secrets and variables → Actions
2. Click on the secret name
3. Click "Update secret"
4. Enter new value

### Want to run it now?

1. Go to Actions tab
2. Click "DOE Weekly Bug Report"
3. Click "Run workflow" → "Run workflow"

---

## 📝 Quick Reference

**Your Repository**: `https://github.com/YOUR_USERNAME/Agentic-Test`

**GitHub Actions**: `https://github.com/YOUR_USERNAME/Agentic-Test/actions`

**Secrets**: `https://github.com/YOUR_USERNAME/Agentic-Test/settings/secrets/actions`

**Schedule**: Every Friday at 7:00 AM UTC

**Recipient**: robin.bhandari@theaccessgroup.com

**Data Files**: Automatically saved in `data/` directory

---

## ⏭️ Next Steps (Optional)

1. **Disable Windows Task Scheduler** (since GitHub Actions is now handling it)
   ```bash
   schtasks /delete /tn "DOE_Weekly_Bug_Report" /f
   ```

2. **Add more recipients** - Edit `execution/send_doe_report.py` line 41

3. **Customize email format** - Edit `execution/send_doe_report.py` HTML template

4. **Add Slack notifications** - Set up a Slack webhook and send to Slack instead/in addition to email

---

**Need help? Check GITHUB_ACTIONS_SETUP.md for detailed troubleshooting!**
