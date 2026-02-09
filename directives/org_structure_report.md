# Organization Structure Report (Excel to HTML)

## Goal
Read an Excel file containing employee data and generate a modern HTML report showing manager-employee relationships, grouped by manager.

## Inputs
Required:
- **Excel File Path**: Path to the Excel file
- **Name Column**: Column name containing employee names
- **Manager Column**: Column name containing manager names (who the employee reports to)

Optional:
- **Output File Path**: Where to save the HTML (default: `.tmp/org_report_[timestamp].html`)
- **Report Title**: Custom title for the HTML page (default: "Organization Structure")

## Tools/Scripts to Use
- `execution/org_structure_report.py` - Script that reads Excel and generates HTML report

## Outputs
- **Format**: HTML file with modern styling
- **Location**: `.tmp/org_report_[timestamp].html` or specified path
- **Structure**:
  - Employees grouped by manager
  - Modern UX with responsive design
  - Clean, professional styling

## Process Flow
1. Read Excel file using pandas/openpyxl
2. Extract Name and Reports To columns
3. Group employees by their manager
4. Generate HTML with modern CSS styling
5. Save to output file
6. Open in browser (optional)

## Edge Cases
- **Missing Managers**: Employees with no manager listed are grouped under "No Manager Assigned"
- **Excel Format Issues**: Script handles both .xlsx and .xls formats
- **Empty Rows**: Automatically skips empty rows
- **Special Characters**: Properly encodes names with special characters in HTML
- **OneDrive Paths**: Handles OneDrive file paths correctly

## Learnings
- OneDrive paths on Windows may include spaces and special characters - ensure proper quoting
- Manager names need exact matching - trim whitespace for consistency

---

**Created**: 2026-01-29
**Last Updated**: 2026-01-29
**Status**: Active
