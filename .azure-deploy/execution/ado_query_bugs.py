"""
Azure DevOps Bug Query Script

Queries Azure DevOps for outstanding (non-closed) bugs in a project.
Returns basic bug information: ID, Title, State, Priority.

Usage:
    python ado_query_bugs.py
    python ado_query_bugs.py --project "MyProject"
    python ado_query_bugs.py --output-file ".tmp/my_bugs.json"
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Azure DevOps SDK
from azure.devops.connection import Connection
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/ado_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def query_bugs(organization_url: str, project_name: str, pat: str) -> dict:
    """
    Query Azure DevOps for outstanding bugs.

    Args:
        organization_url: ADO organization URL (e.g., https://dev.azure.com/yourorg)
        project_name: Project name in ADO
        pat: Personal Access Token for authentication

    Returns:
        dict: Results containing bug list and metadata

    Raises:
        ValueError: If input validation fails
        RuntimeError: If ADO query fails
    """
    logger.info(f"Querying bugs from ADO project: {project_name}")

    try:
        # Step 1: Validate inputs
        if not organization_url:
            raise ValueError("Organization URL cannot be empty")
        if not project_name:
            raise ValueError("Project name cannot be empty")
        if not pat:
            raise ValueError("Personal Access Token cannot be empty")

        # Step 2: Authenticate with ADO
        logger.info("Authenticating with Azure DevOps...")
        credentials = BasicAuthentication("", pat)
        connection = Connection(base_url=organization_url, creds=credentials)

        # Step 3: Get work item tracking client
        wit_client = connection.clients.get_work_item_tracking_client()
        logger.info("Successfully connected to Azure DevOps")

        # Step 4: Build WIQL query for outstanding bugs
        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.State], [Microsoft.VSTS.Common.Priority]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project_name}'
        AND [System.WorkItemType] = 'Bug'
        AND [System.State] <> 'Closed'
        ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.Id] ASC
        """

        # Step 5: Execute WIQL query
        logger.info("Executing WIQL query for bugs...")
        wiql_results = wit_client.query_by_wiql(wiql={"query": wiql_query})

        # Step 6: Extract work item IDs
        if not wiql_results.work_items:
            logger.info("No outstanding bugs found")
            return {
                "status": "success",
                "project": project_name,
                "organization": organization_url,
                "queried_at": datetime.now().isoformat(),
                "bug_count": 0,
                "bugs": [],
            }

        work_item_ids = [item.id for item in wiql_results.work_items]
        logger.info(f"Found {len(work_item_ids)} outstanding bugs")

        # Step 7: Fetch full work item details in batches (API limit is 200 per request)
        logger.info("Fetching bug details...")
        bugs = []
        batch_size = 200

        for i in range(0, len(work_item_ids), batch_size):
            batch_ids = work_item_ids[i : i + batch_size]
            logger.info(
                f"Fetching batch {i//batch_size + 1}/{(len(work_item_ids) + batch_size - 1)//batch_size} ({len(batch_ids)} items)..."
            )

            work_items = wit_client.get_work_items(
                ids=batch_ids, fields=["System.Id", "System.Title", "System.State", "Microsoft.VSTS.Common.Priority"]
            )

            # Step 8: Format results for this batch
            for item in work_items:
                bug_data = {
                    "id": item.id,
                    "title": item.fields.get("System.Title", "N/A"),
                    "state": item.fields.get("System.State", "N/A"),
                    "priority": item.fields.get("Microsoft.VSTS.Common.Priority", "N/A"),
                }
                bugs.append(bug_data)

        result = {
            "status": "success",
            "project": project_name,
            "organization": organization_url,
            "queried_at": datetime.now().isoformat(),
            "bug_count": len(bugs),
            "bugs": bugs,
        }

        logger.info(f"Successfully retrieved {len(bugs)} bugs")
        return result

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error querying Azure DevOps: {e}", exc_info=True)
        error_msg = str(e)

        # Provide helpful error messages
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise RuntimeError(
                f"Authentication failed. Please check your Personal Access Token.\n"
                f"Create a new PAT at: {organization_url}/_usersSettings/tokens\n"
                f"Required scopes: Work Items (Read)\n"
                f"Error: {e}"
            ) from e
        elif "404" in error_msg or "Not Found" in error_msg:
            raise RuntimeError(
                f"Project '{project_name}' not found.\n"
                f"Please verify the project name in your ADO organization.\n"
                f"Error: {e}"
            ) from e
        else:
            raise RuntimeError(f"Failed to query Azure DevOps: {e}") from e


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Query Azure DevOps for outstanding bugs")

    parser.add_argument("--project", type=str, default=None, help="Project name (overrides ADO_PROJECT_NAME from .env)")

    parser.add_argument(
        "--output-file",
        type=str,
        default=f'.tmp/ado_bugs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
        help="Path to output file (default: .tmp/ado_bugs_[timestamp].json)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Load configuration from environment
        organization_url = os.getenv("ADO_ORGANIZATION_URL")
        project_name = args.project or os.getenv("ADO_PROJECT_NAME")
        pat = os.getenv("ADO_PAT")

        # Validate environment variables
        if not organization_url or organization_url == "your_ado_org_url_here":
            raise RuntimeError(
                "ADO_ORGANIZATION_URL not configured in .env file.\n"
                "Please set your Azure DevOps organization URL (e.g., https://dev.azure.com/yourorg)"
            )

        if not project_name or project_name == "your_project_name_here":
            raise RuntimeError(
                "ADO_PROJECT_NAME not configured in .env file.\n"
                "Please set your Azure DevOps project name or use --project flag"
            )

        if not pat or pat == "your_personal_access_token_here":
            raise RuntimeError(
                "ADO_PAT not configured in .env file.\n"
                "Please create a Personal Access Token at:\n"
                f"{organization_url}/_usersSettings/tokens\n"
                "Required scopes: Work Items (Read)"
            )

        # Ensure .tmp directory exists
        os.makedirs(".tmp", exist_ok=True)

        # Run main function
        result = query_bugs(organization_url=organization_url, project_name=project_name, pat=pat)

        # Save output to JSON file
        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {args.output_file}")

        # Print summary to console
        print(f"\n{'='*60}")
        print("Azure DevOps Bug Query Results")
        print(f"{'='*60}")
        print(f"Project: {result['project']}")
        print(f"Organization: {result['organization']}")
        print(f"Query Time: {result['queried_at']}")
        print(f"Outstanding Bugs: {result['bug_count']}")
        print(f"{'='*60}\n")

        if result["bugs"]:
            print(f"{'ID':<10} {'Priority':<10} {'State':<15} {'Title'}")
            print(f"{'-'*10} {'-'*10} {'-'*15} {'-'*50}")
            for bug in result["bugs"]:
                print(f"{bug['id']:<10} {str(bug['priority']):<10} {bug['state']:<15} {bug['title'][:50]}")
        else:
            print("No outstanding bugs found!")

        print(f"\nFull results saved to: {args.output_file}\n")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
