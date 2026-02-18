#!/usr/bin/env python3
"""
Azure DevOps MCP Skill Server

Provides reusable ADO tools via Model Context Protocol.
Replaces duplicated ADO logic across collectors with centralized, tested tools.
"""

from mcp.server import Server
from mcp.types import Tool, TextContent

from skills.ado_skill.tools.query_work_items import query_work_items
from skills.ado_skill.tools.get_work_items_by_ids import get_work_items_by_ids
from skills.ado_skill.tools.get_builds import get_builds
from skills.ado_skill.tools.get_pull_requests import get_pull_requests
from skills.ado_skill.tools.get_test_runs import get_test_runs

# Create MCP server
app = Server("ado-skill")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List all available ADO tools.

    Returns:
        List of Tool definitions with name, description, and parameters
    """
    return [
        Tool(
            name="query_work_items",
            description="Execute WIQL query to search Azure DevOps work items. Supports all work item types (Bug, User Story, Task, etc.). WIQL is validated to prevent injection attacks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization": {
                        "type": "string",
                        "description": "ADO organization name (e.g., 'contoso' from https://dev.azure.com/contoso)"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name"
                    },
                    "wiql": {
                        "type": "string",
                        "description": "WIQL query string (e.g., 'SELECT [System.Id] FROM WorkItems WHERE [System.State] = Active')"
                    }
                },
                "required": ["organization", "project", "wiql"]
            }
        ),
        Tool(
            name="get_work_items_by_ids",
            description="Fetch full details for work items by IDs. Supports batching (max 200 per call). Returns fields like Title, State, AssignedTo, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization": {
                        "type": "string",
                        "description": "ADO organization name"
                    },
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of work item IDs (max 200)"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of fields to retrieve (e.g., ['System.Title', 'System.State']). If omitted, returns all fields."
                    }
                },
                "required": ["organization", "ids"]
            }
        ),
        Tool(
            name="get_builds",
            description="Get build history for a project. Supports filtering by date and pipeline definition.",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization": {
                        "type": "string",
                        "description": "ADO organization name"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name"
                    },
                    "min_time": {
                        "type": "string",
                        "description": "Optional minimum finish time filter (ISO 8601 format, e.g., '2026-01-01T00:00:00Z')"
                    },
                    "max_per_definition": {
                        "type": "integer",
                        "description": "Optional limit per pipeline definition"
                    }
                },
                "required": ["organization", "project"]
            }
        ),
        Tool(
            name="get_pull_requests",
            description="Get pull request history for a repository. Supports filtering by status (active, completed, abandoned).",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization": {
                        "type": "string",
                        "description": "ADO organization name"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name"
                    },
                    "repository_id": {
                        "type": "string",
                        "description": "Repository ID or name"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "abandoned", "all"],
                        "description": "Optional PR status filter"
                    }
                },
                "required": ["organization", "project", "repository_id"]
            }
        ),
        Tool(
            name="get_test_runs",
            description="Get test run history for a project. Returns test execution metadata (duration, pass rate, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization": {
                        "type": "string",
                        "description": "ADO organization name"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum number of runs to retrieve (default: 50)"
                    }
                },
                "required": ["organization", "project"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Execute an ADO tool.

    Args:
        name: Tool name (e.g., "query_work_items")
        arguments: Tool arguments as dictionary

    Returns:
        List of TextContent with JSON results

    Raises:
        ValueError: If tool name is unknown
        SecurityError: If WIQL validation fails
        httpx.HTTPStatusError: If ADO API call fails
    """
    import json

    # Route to appropriate tool
    if name == "query_work_items":
        result = await query_work_items(
            organization=arguments["organization"],
            project=arguments["project"],
            wiql=arguments["wiql"]
        )
    elif name == "get_work_items_by_ids":
        result = await get_work_items_by_ids(
            organization=arguments["organization"],
            ids=arguments["ids"],
            fields=arguments.get("fields")
        )
    elif name == "get_builds":
        result = await get_builds(
            organization=arguments["organization"],
            project=arguments["project"],
            min_time=arguments.get("min_time"),
            max_per_definition=arguments.get("max_per_definition")
        )
    elif name == "get_pull_requests":
        result = await get_pull_requests(
            organization=arguments["organization"],
            project=arguments["project"],
            repository_id=arguments["repository_id"],
            status=arguments.get("status")
        )
    elif name == "get_test_runs":
        result = await get_test_runs(
            organization=arguments["organization"],
            project=arguments["project"],
            top=arguments.get("top", 50)
        )
    else:
        raise ValueError(f"Unknown tool: {name}")

    # Return as TextContent (MCP protocol)
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


if __name__ == "__main__":
    # Start MCP server
    import mcp.server.stdio

    mcp.server.stdio.run(app)
