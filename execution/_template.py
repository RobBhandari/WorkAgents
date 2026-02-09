"""
Template for Execution Scripts

This template demonstrates best practices for creating execution scripts:
- Load environment variables from .env
- Parse command-line arguments
- Set up logging
- Error handling
- Clear docstrings and comments
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/script_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main(input_param: str, optional_param: str = None) -> dict:
    """
    Main function that performs the core logic.

    Args:
        input_param: Description of required parameter
        optional_param: Description of optional parameter

    Returns:
        dict: Results of the operation

    Raises:
        ValueError: If input validation fails
        RuntimeError: If operation fails
    """
    logger.info(f"Starting operation with input: {input_param}")

    try:
        # Step 1: Validate inputs
        if not input_param:
            raise ValueError("input_param cannot be empty")

        # Step 2: Load configuration using secure_config
        from execution.secure_config import ConfigurationError, get_config

        config = get_config()

        # Example: Get Azure DevOps config
        # ado_config = config.get_ado_config()
        # organization_url = ado_config.organization_url
        # pat = ado_config.pat

        # Example: Get ArmorCode config
        # ac_config = config.get_armorcode_config()
        # api_key = ac_config.api_key

        # Example: Get optional environment variable
        # custom_value = config.get_optional_env("YOUR_CUSTOM_VAR", "default_value")

        # Step 3: Perform main operation
        result = {
            "status": "success",
            "input": input_param,
            "processed_at": datetime.now().isoformat(),
            # Add your results here
        }

        logger.info("Operation completed successfully")
        return result

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise RuntimeError(f"Operation failed: {e}") from e


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Description of what this script does")

    parser.add_argument("input_param", type=str, help="Description of required parameter")

    parser.add_argument("--optional-param", type=str, default=None, help="Description of optional parameter")

    parser.add_argument(
        "--output-file", type=str, default=".tmp/output.json", help="Path to output file (default: .tmp/output.json)"
    )

    return parser.parse_args()


if __name__ == "__main__":
    """
    Entry point when script is run from command line.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Run main function
        result = main(input_param=args.input_param, optional_param=args.optional_param)

        # Save output if needed
        import json

        with open(args.output_file, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Results saved to {args.output_file}")

        # Exit with success code
        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
