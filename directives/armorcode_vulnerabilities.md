# ArmorCode Vulnerability Tracking - Operating Charter

## Goal
Track and reduce HIGH and CRITICAL severity vulnerabilities in production from baseline (January 1, 2026) by 70% by June 30, 2026, through systematic tracking, progress monitoring, and automated reporting.

**Success Criteria**: `Vulnerabilities_2026-06-30 ≤ Vulnerabilities_2026-01-01 × 0.30`

## DOE Framework

This operating charter follows the **Directives · Orchestration · Execution** framework:

### **Directives (What to do)**
- **Immutable Baseline**: Vulnerabilities (HIGH + CRITICAL) open on January 1, 2026
- **Target**: Reduce to 30% of baseline by June 30, 2026 (70% reduction)
- **Timeline**: ~180 days (26 weeks) from baseline to target date
- **Scope**: Production environment, specific products/hierarchies, HIGH and CRITICAL severity only

### **Orchestration (Decision making)**
- **Progress Tracking**: Compare current state to baseline
- **Trend Analysis**: Track reduction over time via historical queries
- **Status Reporting**: Generate HTML reports with executive summary and detailed vulnerability listing
- **Communication**: Email reports to stakeholders automatically

### **Execution (Doing the work)**
- **Product Discovery**: Identify available products in ArmorCode
- **Baseline Creation**: Capture immutable snapshot at baseline date
- **Current Query**: Retrieve current vulnerabilities from ArmorCode API
- **Report Generation**: Transform data into visual HTML reports
- **Email Delivery**: Send reports via Microsoft Graph API

## Inputs

### Required Environment Variables (from `.env`):
- **ARMORCODE_API_KEY**: ArmorCode API key for authentication
- **ARMORCODE_BASE_URL**: ArmorCode instance URL (default: `https://app.armorcode.com`)
- **ARMORCODE_ENVIRONMENT**: Environment filter (e.g., `PRODUCTION`)
- **ARMORCODE_PRODUCTS**: Comma-separated list of products to track
- **ARMORCODE_EMAIL_RECIPIENTS**: Email addresses for report distribution
- **ARMORCODE_BASELINE_DATE**: Baseline date (default: `2026-01-01`)
- **ARMORCODE_TARGET_DATE**: Target date (default: `2026-06-30`)
- **ARMORCODE_REDUCTION_GOAL**: Reduction goal as decimal (default: `0.70` for 70%)

### Microsoft Graph API (for email):
- **AZURE_TENANT_ID**: Azure AD tenant ID
- **AZURE_CLIENT_ID**: Azure AD app client ID
- **AZURE_CLIENT_SECRET**: Azure AD app client secret
- **EMAIL_ADDRESS**: Sender email address

### Data Files:
- **`.tmp/armorcode_baseline.json`**: Immutable baseline snapshot (created once)
- **`.tmp/armorcode_tracking.json`**: Historical tracking data (updated with each query)
- **`.tmp/armorcode_products.json`**: Available products list (from discovery)

## Tools/Scripts to Use

### 1. **Product Discovery** (One-time setup)
```bash
python execution/armorcode_list_products.py
```

**Purpose**: Discover available products/hierarchies in ArmorCode

**When to use**:
- Initial setup to identify products for tracking
- When adding new products to tracking scope

**Output**: `.tmp/armorcode_products.json` containing:
- Product IDs and names
- Product hierarchies
- Environment associations

### 2. **Baseline Creation** (One-time setup)
```bash
python execution/armorcode_baseline.py
```

**Purpose**: Create immutable snapshot of vulnerabilities on January 1, 2026

**When to use**:
- First time setup only
- Use `--force` flag to overwrite (NOT RECOMMENDED - baseline should be immutable)

**Output**: `.tmp/armorcode_baseline.json` containing:
- Baseline date and count
- Target count (30% of baseline)
- Required weekly reduction rate
- Full vulnerability details

### 3. **Vulnerability Query and Comparison**
```bash
python execution/armorcode_query_vulns.py
```

**Purpose**: Query current vulnerabilities and compare to baseline

**When to use**:
- Every reporting cycle (scheduled or manual)
- Can output summary or full JSON format

**Output**:
- Console summary showing progress
- Updates `.tmp/armorcode_tracking.json` with current data point
- Saves detailed query to `.tmp/armorcode_query_[timestamp].json`

### 4. **HTML Report Generation**
```bash
python execution/armorcode_report_to_html.py .tmp/armorcode_query_[timestamp].json
```

**Purpose**: Generate styled HTML report from query data

**When to use**:
- After running query to create visual report
- Automatically called by batch workflow

**Output**: `.tmp/armorcode_report_[timestamp].html` with:
- Executive summary card
- Progress metrics
- Trend chart (if historical data available)
- Full vulnerability table
- Statistics by severity, product, and status

### 5. **Email Report Delivery**
```bash
python execution/send_armorcode_report.py .tmp/armorcode_report_[timestamp].html --json-summary .tmp/armorcode_query_[timestamp].json
```

**Purpose**: Send HTML report via email to stakeholders

**When to use**:
- After generating HTML report
- Automatically called by batch workflow

**Output**:
- Email sent with HTML attachment
- Email body includes text summary of key metrics

### 6. **Full Workflow (Recommended)**
```bash
cd execution
run_armorcode_report.bat
```

**Purpose**: Run complete workflow (query → HTML → email)

**When to use**:
- Regular reporting cycles
- Scheduled task execution

**Output**: Complete report cycle with all artifacts

## Outputs

### Console Reports
- Summary showing baseline, target, current count
- Reduction metrics (amount, percentage, progress to goal)
- Timeline (days since baseline, days to target)

### HTML Reports
Comprehensive visual report with:
- **Executive Summary**: Large, prominent display of key metrics
  - Baseline count
  - Target count
  - Current count
  - Reduction achieved
  - Progress to goal
  - Timeline information

- **Statistics Cards**: Quick view of:
  - Total vulnerabilities
  - Critical count (red)
  - High count (orange)
  - Number of products

- **Trend Chart**: Historical visualization (when data available)
  - Date, count, % of baseline
  - Visual progress bars

- **Vulnerability Table**: Detailed listing
  - Sortable by severity, product, title, CVE/CWE, status, date
  - Searchable
  - Color-coded severity badges
  - Expandable details

### Email Reports
**Subject**: `ArmorCode Vulnerability Report - [Date] - [Count] vulns ([Progress]% to goal)`

**Body**: Text summary with:
- Baseline, target, current counts
- Reduction metrics
- Progress percentages
- Timeline information

**Attachment**: HTML report file

### Data Files
**`.tmp/armorcode_baseline.json`**: Immutable baseline
```json
{
  "baseline_date": "2026-01-01",
  "vulnerability_count": 140,
  "target_count": 42,
  "reduction_goal": 0.70,
  "required_weekly_reduction": 3.77,
  "vulnerabilities": [...]
}
```

**`.tmp/armorcode_tracking.json`**: Historical tracking
```json
{
  "queries": [
    {
      "date": "2026-01-30",
      "count": 120,
      "reduction_pct": 14.3,
      "progress_to_goal_pct": 20.4
    }
  ]
}
```

## Process Flow

### Initial Setup (One-time)

1. **Obtain ArmorCode API Key**
   - Log in to ArmorCode platform
   - Navigate to Settings > API Keys
   - Click "Generate New Key"
   - Configure permissions: Read access for vulnerabilities/findings
   - Copy API key
   - Add to `.env`: `ARMORCODE_API_KEY=your_key_here`

2. **Discover Products**
   ```bash
   python execution/armorcode_list_products.py
   ```
   - Review output: `.tmp/armorcode_products.json`
   - Identify products to track
   - Update `.env`: `ARMORCODE_PRODUCTS=Product1,Product2,Product3`

3. **Create Baseline**
   ```bash
   python execution/armorcode_baseline.py
   ```
   - Verify `.tmp/armorcode_baseline.json` exists
   - Confirm baseline_date = "2026-01-01"
   - Note vulnerability count and target count
   - Note required weekly reduction rate

4. **Configure Email Recipients**
   - Update `.env`: `ARMORCODE_EMAIL_RECIPIENTS=email1@company.com,email2@company.com`

### Regular Reporting (Manual or Scheduled)

1. **Run Full Workflow**
   ```bash
   cd execution
   run_armorcode_report.bat
   ```
   - Step 1: Queries current vulnerabilities from ArmorCode
   - Step 2: Generates HTML report with comparison to baseline
   - Step 3: Sends email with HTML attachment

2. **Review Report**
   - Check email for report
   - Open HTML attachment
   - Review executive summary for progress
   - Check vulnerability table for details
   - Review trend chart for historical context

3. **Take Action**
   - Prioritize vulnerabilities based on severity
   - Assign remediation tasks
   - Track closure progress
   - Investigate if progress is below target

## Automated Scheduling

### Set Up Scheduled Task (Windows Task Scheduler)

**Option 1: Manual Setup via Task Scheduler GUI**

1. Open Task Scheduler (`Win+R` → `taskschd.msc`)
2. Click "Create Basic Task"
3. Name: `ArmorCode_Vulnerability_Report`
4. Trigger: Configure your desired schedule (e.g., Weekly on Monday 8:00 AM)
5. Action: Start a program
   - Program: `cmd.exe`
   - Arguments: `/c "c:\DEV\Agentic-Test\execution\run_armorcode_report.bat"`
   - Start in: `c:\DEV\Agentic-Test`
6. Finish and enter Windows password if prompted

**Option 2: PowerShell Setup**
```powershell
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "c:\DEV\Agentic-Test\execution\run_armorcode_report.bat"' -WorkingDirectory "c:\DEV\Agentic-Test"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 8am
Register-ScheduledTask -TaskName "ArmorCode_Vulnerability_Report" -Action $action -Trigger $trigger -Description "ArmorCode vulnerability tracking report"
```

### Managing the Scheduled Task

**View task status:**
```powershell
Get-ScheduledTask -TaskName "ArmorCode_Vulnerability_Report"
```

**Run task immediately (test):**
```powershell
Start-ScheduledTask -TaskName "ArmorCode_Vulnerability_Report"
```

**Check logs:**
```batch
type .tmp\armorcode_query_*.log
type .tmp\armorcode_html_*.log
type .tmp\send_armorcode_report_*.log
```

**Disable/Enable task:**
```powershell
Disable-ScheduledTask -TaskName "ArmorCode_Vulnerability_Report"
Enable-ScheduledTask -TaskName "ArmorCode_Vulnerability_Report"
```

## Metrics Explained

### **Baseline Count**
Number of HIGH and CRITICAL vulnerabilities open on January 1, 2026

### **Target Count**
30% of baseline (representing 70% reduction goal)

### **Current Count**
Number of HIGH and CRITICAL vulnerabilities currently open

### **Reduction Amount**
`Reduction = Baseline - Current`

### **Reduction Percentage**
`Reduction % = (Reduction Amount / Baseline) × 100`

### **Remaining to Goal**
`Remaining = Current - Target`

### **Progress to Goal**
`Progress % = (Reduction Amount / (Baseline - Target)) × 100`
- Represents how far along we are toward the 70% reduction goal

### **Timeline Metrics**
- **Days Since Baseline**: Days elapsed since January 1, 2026
- **Days to Target**: Days remaining until June 30, 2026

## Edge Cases

### **Baseline Missing**
**Symptom**: Query fails with "Baseline not found"

**Resolution**:
```bash
python execution/armorcode_baseline.py
```
Baseline must be created before running queries.

### **Baseline Already Exists**
**Symptom**: Baseline script fails with "Baseline already exists and is immutable"

**Why**: Baseline should never be overwritten to ensure consistent tracking

**Resolution**:
- If baseline is correct: No action needed, this is expected behavior
- If baseline must be recreated: Use `--force` flag (NOT RECOMMENDED)
  ```bash
  python execution/armorcode_baseline.py --force
  ```

### **API Authentication Failure**
**Symptom**: Scripts fail with authentication error

**Common Causes**:
1. ARMORCODE_API_KEY not set or incorrect
2. API key expired
3. API key lacks required permissions

**Resolution**:
1. Verify `.env` configuration
2. Regenerate API key in ArmorCode UI
3. Ensure key has read permissions for vulnerabilities

### **No Products Configured**
**Symptom**: Warning about no products configured

**Impact**: Query will include ALL products (may not be desired)

**Resolution**:
1. Run product discovery: `python execution/armorcode_list_products.py`
2. Update `.env`: `ARMORCODE_PRODUCTS=Product1,Product2`

### **Email Send Failure**
**Symptom**: SMTP or Graph API error

**Common Causes**:
1. Microsoft Graph credentials not configured
2. Sender email not authorized
3. Network/firewall blocking

**Resolution**:
1. Verify `.env` Graph API configuration
2. Test Graph API permissions
3. Check network connectivity

### **ArmorCode SDK Not Found**
**Symptom**: Import error for acsdk

**Resolution**:
```bash
pip install acsdk
# or
pip install -r requirements.txt
```

### **No Vulnerabilities Found**
**Symptom**: Query returns 0 vulnerabilities

**Possible Reasons**:
1. All vulnerabilities remediated (good news!)
2. Wrong environment filter
3. Wrong product filter
4. API filter issue

**Resolution**:
1. Verify `.env` filters (ARMORCODE_ENVIRONMENT, ARMORCODE_PRODUCTS)
2. Test query in ArmorCode UI with same filters
3. Check logs for API response details

### **Trend Chart Not Showing**
**Symptom**: HTML report missing trend chart

**Reason**: Need at least 2 data points in tracking history

**Resolution**: Run query multiple times to build historical data

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Obtain ArmorCode API Key

**Location**: ArmorCode UI → **Manage** (left sidebar) → **Integrations** → **ArmorCode API**

**Steps**:
1. Log in to ArmorCode: https://app.armorcode.com (or your instance URL)
2. Click **"Manage"** in the left sidebar
3. Click **"Integrations"**
4. Select **"ArmorCode API"**
5. Click **"Create New Key"** button (top right)
6. Fill in the form:
   - **Token Name**: "Vulnerability_Tracking_Script_[YourName]"
   - **API Role**: "Read Only"
   - **Product**: "All" (or specific products)
   - **Expiry**: 90+ days (or as per policy)
   - **Account Level Access**: "No" (unless org-wide access needed)
7. Click **"Generate"** or **"Create"**
8. **IMPORTANT**: Copy the full API key immediately (it won't be shown again!)

**Note**: If you don't have permission to create API keys (see "No access" message), contact your ArmorCode administrator to create one for you with the specifications above.

### 3. Configure Environment Variables
Edit `.env` file:
```bash
# ArmorCode Configuration
ARMORCODE_API_KEY=your_actual_api_key_here
ARMORCODE_BASE_URL=https://app.armorcode.com
ARMORCODE_ENVIRONMENT=PRODUCTION
ARMORCODE_PRODUCTS=
ARMORCODE_EMAIL_RECIPIENTS=your_email@company.com
ARMORCODE_BASELINE_DATE=2026-01-01
ARMORCODE_TARGET_DATE=2026-06-30
ARMORCODE_REDUCTION_GOAL=0.70

# Microsoft Graph API (for email)
AZURE_TENANT_ID=your_tenant_id_here
AZURE_CLIENT_ID=your_client_id_here
AZURE_CLIENT_SECRET=your_client_secret_here
EMAIL_ADDRESS=sender@company.com
```

### 4. Discover Products
```bash
python execution/armorcode_list_products.py
```
Review output and update ARMORCODE_PRODUCTS in `.env`

### 5. Create Baseline
```bash
python execution/armorcode_baseline.py
```
Verify baseline created successfully

### 6. Test Full Workflow
```bash
cd execution
run_armorcode_report.bat
```
Check for:
- Query JSON file in `.tmp/`
- HTML report in `.tmp/`
- Email received

### 7. Set Up Scheduling (Optional)
Follow instructions in "Automated Scheduling" section above

## Learnings

### **SDK Method Variations**
- ArmorCode SDK methods may vary by version
- Scripts include fallback methods for common patterns
- Consult SDK documentation if methods change: https://github.com/armor-code/acsdk

### **Baseline Immutability**
- Never overwrite baseline to maintain consistent tracking
- If baseline date needs to change, backup old baseline first

### **Tracking History**
- Builds over time with each query execution
- Enables trend visualization
- Stored in `.tmp/armorcode_tracking.json`
- Consider backing up to cloud storage

### **Report Accessibility**
- HTML reports are fully self-contained
- Can be opened offline or forwarded
- Includes search and sort functionality

### **Email Delivery**
- Microsoft Graph API more reliable than SMTP for corporate email
- Subject line includes key metrics for inbox scanning
- HTML attachment preserves full formatting

---

**Created**: 2026-01-30
**Last Updated**: 2026-01-30
**Status**: Active
**Framework**: DOE (Directives · Orchestration · Execution)
