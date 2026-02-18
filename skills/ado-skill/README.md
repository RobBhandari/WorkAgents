# Azure DevOps MCP Skill

**Version**: 1.0.0
**Protocol**: Model Context Protocol (MCP)

## Overview

This MCP skill provides reusable tools for interacting with Azure DevOps REST API v7.1. It replaces duplicated logic across multiple collectors with a single, well-tested, maintainable skill.

## Why This Exists

**Problem**: 9 collectors (quality, security, flow, deployment, etc.) all duplicate the same ADO query logic (~650 lines each). Total duplication: ~5,850 lines.

**Solution**: Extract common ADO logic into reusable MCP tools. Collectors become thin wrappers (100-150 lines) that call skill tools.

**Benefits**:
- **83% code reduction**: 5,850 lines → 850 lines (skills + thin collectors)
- **Single source of truth**: Fix auth bug once, all collectors benefit
- **Easier testing**: Test skills independently of collectors
- **Easier to swap**: Replace ADO with GitHub/GitLab by swapping skill

## Architecture

```
Collectors (9 files, 100 lines each)
    ↓
  calls
    ↓
ADO Skill (1 skill, 10 tools, 500 lines total)
    ↓
  queries
    ↓
Azure DevOps REST API v7.1
```

## Tools Provided

### Work Item Tools
- `query_work_items` - Execute WIQL query (with injection prevention)
- `get_work_items_by_ids` - Fetch work items by IDs (batched)

### Build Tools
- `get_builds` - Get build history
- `get_build_changes` - Get commits for a build

### Git Tools
- `get_repositories` - List repositories
- `get_pull_requests` - Get PR history
- `get_commits` - Get commit history

### Test Tools
- `get_test_runs` - Get test run history

## Usage Example

```python
from mcp.client import Client

# Connect to ADO skill
ado = Client("ado-skill")

# Query bugs (WIQL validated automatically)
bugs = await ado.call_tool(
    "query_work_items",
    organization="myorg",
    project="MyProject",
    wiql="SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = 'Bug'"
)

# Get PR history
prs = await ado.call_tool(
    "get_pull_requests",
    organization="myorg",
    project="MyProject",
    repository_id="my-repo",
    status="completed"
)
```

## Security

- **WIQL Injection Prevention**: All queries validated via `WIQLValidator`
- **TLS 1.2+**: HTTPS-only connections
- **Rate Limiting**: Automatic retry with exponential backoff
- **Auth**: PAT-based Basic Auth (Base64 encoded)

## Testing

```bash
# Run skill tests
pytest skills/ado-skill/tests/ -v

# Run with coverage
pytest skills/ado-skill/tests/ --cov=skills/ado-skill --cov-report=term
```

## Configuration

Set these environment variables:

```bash
ADO_ORGANIZATION_URL=https://dev.azure.com/myorg
ADO_PAT=your-personal-access-token
```

Or use `.env` file (recommended):

```
ADO_ORGANIZATION_URL=https://dev.azure.com/myorg
ADO_PAT=your-personal-access-token
```

## Dependencies

- `httpx` - Async HTTP client with HTTP/2 support
- `python-dotenv` - Environment variable management
- `mcp` - Model Context Protocol SDK

## API Documentation

Azure DevOps REST API v7.1:
https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.1
