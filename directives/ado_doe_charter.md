# DOE Operating Charter - Bug Backlog Reduction

## Goal
Reduce the Azure DevOps open customer bug backlog from baseline (Week 0) to ≤ 30% by June 30, 2026, through systematic tracking, burn-down management, and weekly status reporting.

**Success Criteria**: `OpenBacklog_2026-06-30 ≤ OpenBacklog_0 × 0.30`

## DOE Framework

This operating charter follows the **Directives · Orchestration · Execution** framework:

### **Directives (What to do)**
- **Immutable Baseline**: Bugs open on January 1, 2026 (Week 0)
- **Target**: Reduce to 30% of baseline by June 30, 2026
- **Timeline**: 26 weeks from baseline to target date
- **Status Indicators**:
  - 🟢 **GREEN**: Actual ≤ Expected (on track)
  - 🟠 **AMBER**: Actual ≤ Expected × 1.10 (warning)
  - 🔴 **RED**: Actual > Expected × 1.10 (action required)

### **Orchestration (Decision making)**
- **Weekly Metrics**: Calculate Open, New, Closed, Net Burn
- **Burn-down Math**: Track actual vs expected progress
- **Status Determination**: Apply GREEN/AMBER/RED logic
- **Reporting**: Email weekly status to stakeholders

### **Execution (Doing the work)**
- **Triage**: Categorize and prioritize bugs
- **Ownership**: Assign bugs to engineers
- **WIP Limits**: Cap concurrent bug fixes
- **Validation**: Test and close bugs

## Inputs

### Required Environment Variables (from `.env`):
- **ADO_ORGANIZATION_URL**: Azure DevOps organization URL (e.g., `https://dev.azure.com/yourorg`)
- **ADO_PROJECT_NAME**: Project name in ADO
- **ADO_PAT**: Personal Access Token with Work Items (Read) permissions
- **EMAIL_ADDRESS**: Gmail sender address
- **EMAIL_PASSWORD**: Gmail App Password
- **SMTP_SERVER**: SMTP server (default: `smtp.gmail.com`)
- **SMTP_PORT**: SMTP port (default: `587`)

### Data Files:
- **`.tmp/baseline.json`**: Immutable Week 0 baseline snapshot (created once)
- **`.tmp/weekly_tracking.json`**: Historical weekly tracking data (updated weekly)

## Tools/Scripts to Use

### 1. **Baseline Creation** (One-time setup)
```bash
python execution/ado_baseline.py
```

**Purpose**: Create immutable snapshot of bugs open on January 1, 2026

**When to use**:
- First time setup only
- Use `--force` flag to overwrite (NOT RECOMMENDED - baseline should be immutable)

**Output**: `.tmp/baseline.json` containing:
- Baseline date (2026-01-01)
- Open bug count at baseline
- Target count (30% of baseline)
- Required weekly burn rate

### 2. **Weekly Metrics Calculation**
```bash
python execution/ado_doe_tracker.py
```

**Purpose**: Calculate current week's metrics and status

**When to use**:
- Every week to track progress
- Can override week number with `--week-number N`

**Output**:
- Console report showing weekly summary
- Updates `.tmp/weekly_tracking.json` with current week's data
- Can output JSON format with `--output-format json`

### 3. **Email Reporting**
```bash
python execution/send_doe_report.py
```

**Purpose**: Send weekly DOE report via email

**When to use**:
- After running DOE tracker to send status update
- Use `--dry-run` to preview email without sending
- Can override recipient with `--recipient email@address.com`

**Output**:
- Formatted email with status indicators and metrics
- Sent to: robin.bhandari@theaccessgroup.com (default)

## Outputs

### Console Reports
- Weekly summary with status indicator
- Metrics: Open, New, Closed, Net Burn
- Progress: Actual vs Expected
- Timeline: Weeks elapsed and remaining

### Email Reports
**Subject**: `Bug Position - ALCM - Week N`

**Content**:
```
Weekly Summary
==============
Starting (Week 0):     [baseline_count]
Target (30%):          [target_count]
Expected this week:    [expected_count]
Actual:                [actual_count] [status_emoji]

New: [new] | Closed: [closed] | Net burn: [net_burn]
Required burn: +[required_burn]

Status: [GREEN/AMBER/RED] [emoji]
Weeks remaining: [weeks_remaining]
Target date: 2026-06-30
```

### Data Files
**`.tmp/baseline.json`**: Immutable baseline (created once)
```json
{
  "baseline_date": "2026-01-01",
  "baseline_week": 0,
  "open_count": 280,
  "target_count": 84,
  "required_weekly_burn": 7.54
}
```

**`.tmp/weekly_tracking.json`**: Historical data (updated weekly)
```json
{
  "weeks": [
    {
      "week_number": 1,
      "open": 268,
      "new": 11,
      "closed": 18,
      "net_burn": 7,
      "expected": 266,
      "status": "GREEN",
      "delta": -2
    }
  ]
}
```

## Process Flow

### Week 0: Initial Setup
1. **Create Baseline** (one-time)
   ```bash
   python execution/ado_baseline.py
   ```
2. **Verify Baseline**
   - Check `.tmp/baseline.json` exists
   - Confirm baseline_date = "2026-01-01"
   - Verify open_count reflects bugs open on Jan 1, 2026
   - Note required_weekly_burn rate

### Weekly: Status Tracking (Run every week)
1. **Calculate Metrics**
   ```bash
   python execution/ado_doe_tracker.py
   ```
   - Queries current open bugs from ADO
   - Calculates new bugs created this week
   - Calculates bugs closed this week
   - Determines net burn and status
   - Updates weekly tracking file

2. **Send Report**
   ```bash
   python execution/send_doe_report.py
   ```
   - Formats weekly summary
   - Applies status color coding
   - Sends email to stakeholders

3. **Review Status**
   - 🟢 **GREEN**: Continue current pace
   - 🟠 **AMBER**: Monitor closely, consider increasing capacity
   - 🔴 **RED**: Immediate action required, escalate

### Monthly: Trajectory Review
1. Review 4-week trend in `.tmp/weekly_tracking.json`
2. Calculate average net burn over past month
3. Project final count at target date
4. Adjust team capacity if needed

## Automated Scheduling

### Set Up Weekly Email (7am Every Friday)

**✨ Auto-Schedule (Built-in)**

The system will **automatically attempt to schedule itself** after your first successful email send. Simply run:

```batch
cd c:\DEV\Agentic-Test\execution
run_weekly_doe_report.bat
```

If you have admin rights, the script will automatically create the Friday 7am scheduled task. If not, you'll be prompted to run the setup manually as Administrator.

**Option 1: Manual Admin Setup (If Auto-Schedule Fails)**

If the auto-schedule requires admin rights, run this as Administrator:
```batch
# Right-click and select "Run as Administrator"
cd c:\DEV\Agentic-Test\execution
schedule_doe_report.bat
```

Or use PowerShell:
```powershell
# Right-click PowerShell and select "Run as Administrator"
cd c:\DEV\Agentic-Test\execution
.\setup_scheduled_task.ps1
```

**Option 2: Manual Setup via Task Scheduler GUI**

1. Open Task Scheduler (`Win+R` → `taskschd.msc`)
2. Click "Create Basic Task"
3. Name: `DOE_Weekly_Bug_Report`
4. Trigger: Weekly, Friday, 7:00 AM
5. Action: Start a program
   - Program: `cmd.exe`
   - Arguments: `/c "c:\DEV\Agentic-Test\execution\run_weekly_doe_report.bat"`
   - Start in: `c:\DEV\Agentic-Test`
6. Finish and enter your Windows password if prompted

### Managing the Scheduled Task

**View task status:**
```powershell
Get-ScheduledTask -TaskName "DOE_Weekly_Bug_Report"
```

**Run task immediately (test):**
```powershell
Start-ScheduledTask -TaskName "DOE_Weekly_Bug_Report"
```

**View task history:**
```powershell
Get-ScheduledTaskInfo -TaskName "DOE_Weekly_Bug_Report"
```

**Check logs:**
```batch
type .tmp\scheduled_doe_report.log
```

**Disable task:**
```powershell
Disable-ScheduledTask -TaskName "DOE_Weekly_Bug_Report"
```

**Enable task:**
```powershell
Enable-ScheduledTask -TaskName "DOE_Weekly_Bug_Report"
```

**Remove task:**
```powershell
Unregister-ScheduledTask -TaskName "DOE_Weekly_Bug_Report" -Confirm:$false
```

## Metrics Explained

### **Open**
Current count of bugs in non-Closed state in Azure DevOps

### **New**
Bugs created during the current week (System.CreatedDate within week range)

### **Closed**
Bugs moved to Closed state during the current week (Microsoft.VSTS.Common.ClosedDate within week range)

### **Net Burn**
`Net Burn = Closed - New`
- Positive = making progress (closing more than creating)
- Negative = falling behind (creating more than closing)

### **Expected**
Calculated as: `Baseline - (Required_Weekly_Burn × Weeks_Elapsed)`
- Represents where we should be if on track
- Cannot go below target count (30% of baseline)

### **Delta**
`Delta = Actual - Expected`
- Negative = ahead of schedule
- Positive = behind schedule

### **Status**
- 🟢 **GREEN**: `Actual ≤ Expected`
- 🟠 **AMBER**: `Expected < Actual ≤ Expected × 1.10`
- 🔴 **RED**: `Actual > Expected × 1.10`

## Edge Cases

### **Baseline Missing**
**Symptom**: DOE tracker fails with "Baseline not found"

**Resolution**:
```bash
python execution/ado_baseline.py
```
Baseline must be created before running tracker.

### **Baseline Already Exists**
**Symptom**: Baseline script fails with "Baseline already exists and is immutable"

**Why**: Baseline should never be overwritten to ensure consistent tracking

**Resolution**:
- If baseline is correct: No action needed, this is expected behavior
- If baseline must be recreated: Use `--force` flag (NOT RECOMMENDED)
  ```bash
  python execution/ado_baseline.py --force
  ```

### **Negative Net Burn**
**Symptom**: Net burn is negative (more bugs created than closed)

**Impact**: Automatically triggers RED status

**Resolution**:
1. Investigate why new bugs increased
2. Prioritize bug triage and closure
3. Consider WIP limits or dedicated bug sprint
4. Escalate to management

### **RED Status**
**Symptom**: Actual count > Expected × 1.10

**Impact**: Falling significantly behind target trajectory

**Resolution**:
1. Immediate team review
2. Identify blockers preventing bug closure
3. Increase team capacity for bug fixes
4. Consider pausing new feature work
5. Weekly check-ins until back to GREEN/AMBER

### **Email Send Failure**
**Symptom**: SMTP authentication error or connection timeout

**Common Causes**:
1. EMAIL_PASSWORD not set or incorrect
2. Gmail App Password not created
3. SMTP_SERVER or SMTP_PORT misconfigured
4. Network/firewall blocking SMTP

**Resolution**:
1. Verify `.env` configuration
2. Create Gmail App Password: https://myaccount.google.com/apppasswords
3. Test with `--dry-run` flag first
4. Check firewall/network settings

### **Week Number Mismatch**
**Symptom**: Auto-calculated week number seems incorrect

**Resolution**: Override week number manually
```bash
python execution/ado_doe_tracker.py --week-number 5
```

### **Large Result Sets**
**Symptom**: Queries taking a long time with hundreds of bugs

**Expected**: Azure DevOps SDK handles pagination automatically

**If Performance Issues**:
- Baseline query runs once (acceptable)
- Weekly queries are fast (only checking date ranges)
- No action needed unless timeout occurs

### **Missing Bug Fields**
**Symptom**: Some bugs missing Priority or other fields

**Resolution**: Script handles missing fields gracefully with "N/A" values

**No Action Required**: Tracking still accurate based on bug counts

## Setup Instructions

### 1. Create Azure DevOps Personal Access Token
1. Go to: `https://dev.azure.com/[your-org]/_usersSettings/tokens`
2. Click "New Token"
3. Name: "DOE Bug Tracker"
4. Organization: Select your organization
5. Scopes: **Work Items (Read)**
6. Expiration: Set as needed (recommend 90 days)
7. Copy the generated PAT immediately

### 2. Create Gmail App Password
1. Go to: https://myaccount.google.com/apppasswords
2. Select "Mail" and "Other (Custom name)"
3. Name: "DOE Bug Tracker"
4. Click "Generate"
5. Copy the 16-character password

### 3. Configure Environment Variables
Edit `.env` file:
```bash
# Azure DevOps Configuration
ADO_ORGANIZATION_URL=https://dev.azure.com/yourorg
ADO_PROJECT_NAME=YourProjectName
ADO_PAT=your_generated_pat_token

# Email Configuration
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_16_char_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Create Baseline (Week 0)
```bash
python execution/ado_baseline.py
```

### 6. Test Weekly Workflow
```bash
# Calculate metrics
python execution/ado_doe_tracker.py

# Preview email (don't send)
python execution/send_doe_report.py --dry-run

# Send actual email
python execution/send_doe_report.py
```

## Learnings

### **Baseline Date Calculation**
- Baseline represents bugs open at START of January 1, 2026
- Query uses `CreatedDate < '2026-01-01'` (not `<=`) to capture bugs existing before that day
- Bugs closed on/after Jan 1 are included (they were open at baseline)

### **Week Numbering**
- Week 0 = Baseline (January 1, 2026)
- Week 1 = First week of tracking (Jan 1-7, 2026)
- Week N auto-calculated from baseline date
- Can override with `--week-number` for historical analysis

### **Required Burn Rate**
- Calculated as: `(Baseline - Target) / Weeks_to_Target`
- This is the AVERAGE burn needed per week
- Actual weekly burn will vary, status tracks cumulative progress

### **Status Amber Threshold**
- 10% buffer allows for weekly variation
- Prevents unnecessary status flipping
- Provides early warning before RED

### **Email Formatting**
- Both plain text and HTML versions included
- HTML uses color coding for visual clarity
- Status emoji works in most email clients

### **Data Persistence**
- Baseline is immutable for consistency
- Weekly tracking preserves historical data
- Both files in `.tmp/` for easy cleanup
- Consider backing up to cloud storage

---

**Created**: 2026-01-30
**Last Updated**: 2026-01-30
**Status**: Active
**Owner**: Engineering Team
**Stakeholder**: robin.bhandari@theaccessgroup.com
