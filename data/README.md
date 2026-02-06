# AI Usage Data

## Overview
This directory contains the source data file for the AI Usage Report dashboard.

## File: ai_usage_data.csv
- **Source**: `C:\Users\Robin.Bhandari\OneDrive - Access UK Ltd\__LEGAL\Delta Master Tracker\AI - Delta P & E People.csv`
- **Update Frequency**: Weekly (every Monday recommended)
- **Purpose**: Tracks Claude and Devin usage across the organization

## Weekly Update Workflow

1. **Copy Latest Data**
   ```bash
   cp "C:\Users\Robin.Bhandari\OneDrive - Access UK Ltd\__LEGAL\Delta Master Tracker\AI - Delta P & E People.csv" data/ai_usage_data.csv
   ```

2. **Commit Changes**
   ```bash
   git add data/ai_usage_data.csv
   git commit -m "Update AI usage data - [date]"
   git push
   ```

3. **Automated Report Generation**
   - GitHub Actions will automatically detect the update
   - The workflow runs `execution/usage_tables_report.py`
   - Generates updated HTML dashboard
   - Available in `.tmp/observatory/dashboards/usage_tables_latest.html`

## Manual Report Generation

To generate the report manually:

```bash
python execution/usage_tables_report.py
python execution/usage_tables_report.py --open  # Opens in browser
```

## Data Structure

The CSV must contain these columns:
- `Name` - User name
- `Job Title` - User's job title
- `Software Company` - Company/division (filtered for 'LGL')
- `Claude Access?` - Access status (Yes/No)
- `Claude 30 day usage` - Usage count for last 30 days
- `Devin Access?` - Access status (Yes/No)
- `Devin_30d` - Devin usage count for last 30 days
