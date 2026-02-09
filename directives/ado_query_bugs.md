# Query Azure DevOps Bugs

## Goal
Query Azure DevOps for outstanding (non-closed) bugs in a project and return basic bug information (ID, Title, State, Priority).

## Inputs
Required inputs (from `.env`):
- **ADO_ORGANIZATION_URL**: Azure DevOps organization URL (e.g., `https://dev.azure.com/yourorg`)
- **ADO_PROJECT_NAME**: Project name in ADO (can be overridden with `--project` flag)
- **ADO_PAT**: Personal Access Token with Work Items (Read) permissions

Optional inputs:
- **--project**: Override project name from command line
- **--output-file**: Custom output file path (default: `.tmp/ado_bugs_[timestamp].json`)

## Tools/Scripts to Use
- `execution/ado_query_bugs.py` - Python script that connects to Azure DevOps, queries for bugs using WIQL, and returns structured results

## Outputs
**Format**: JSON file saved to `.tmp/` directory

**Structure**:
```json
{
  "status": "success",
  "project": "ProjectName",
  "organization": "https://dev.azure.com/yourorg",
  "queried_at": "2026-01-29T12:34:56.789012",
  "bug_count": 5,
  "bugs": [
    {
      "id": 12345,
      "title": "Bug description",
      "state": "Active",
      "priority": 1
    }
  ]
}
```

**Console Output**: Pretty-printed table with bug summary

## Process Flow
1. **Load Configuration**: Read ADO credentials from `.env` file
2. **Validate Inputs**: Check that all required environment variables are set
3. **Authenticate**: Connect to Azure DevOps using Personal Access Token (PAT)
4. **Query Bugs**: Execute WIQL query to find all non-closed bugs
5. **Fetch Details**: Retrieve full work item details for each bug ID
6. **Format Results**: Structure data with ID, Title, State, Priority
7. **Save Output**: Write JSON to `.tmp/` directory and display summary

## Edge Cases

### **Authentication Errors**
- **Missing PAT**: Script checks for placeholder values and provides setup instructions
- **Invalid PAT**: Returns 401 error with link to create new token
- **Expired PAT**: Same as invalid PAT - regenerate token
- **Insufficient Permissions**: Ensure PAT has "Work Items (Read)" scope

### **Connection Issues**
- **Invalid Organization URL**: Returns 404 error with verification message
- **Network Timeout**: Azure DevOps SDK handles retries automatically
- **Project Not Found**: Returns 404 with message to verify project name

### **Query Results**
- **No Bugs Found**: Returns success with empty bug list and count of 0
- **Large Result Sets**: WIQL query automatically handles pagination
- **Missing Fields**: Returns "N/A" for any missing bug fields

### **Configuration Issues**
- **Missing .env File**: Script fails with clear message about required variables
- **Placeholder Values**: Detects default placeholder values and prompts for real credentials
- **.tmp Directory**: Script creates directory if it doesn't exist

## Setup Instructions

### 1. Create Personal Access Token
1. Go to: `https://dev.azure.com/[your-org]/_usersSettings/tokens`
2. Click "New Token"
3. Name: "Bug Query Script"
4. Organization: Select your organization
5. Scopes: Work Items (Read)
6. Expiration: Set as needed
7. Copy the generated PAT immediately (can't view it again)

### 2. Configure Environment Variables
Edit `.env` file:
```bash
ADO_ORGANIZATION_URL=https://dev.azure.com/yourorg
ADO_PROJECT_NAME=YourProjectName
ADO_PAT=your_generated_pat_token
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Query
```bash
python execution/ado_query_bugs.py
```

## Learnings
- **WIQL Syntax**: Azure DevOps uses Work Item Query Language. Field names must be exact (e.g., `[System.State]`, `[Microsoft.VSTS.Common.Priority]`)
- **PAT Authentication**: Use `BasicAuthentication` with empty username and PAT as password
- **Bug States**: Common states are "New", "Active", "Resolved", "Closed". Query excludes "Closed" by default
- **Priority Field**: Not all ADO configurations use the same priority field. Some may use custom fields
- **Performance**: Query fetches IDs first (fast), then retrieves details (slower for large result sets)

---

**Created**: 2026-01-29
**Last Updated**: 2026-01-29
**Status**: Active
