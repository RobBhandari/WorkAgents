#!/usr/bin/env python3
"""
Agent Runner Script

Executes autonomous collector agents.
Used by GitHub Actions workflows to run agents instead of legacy collectors.

Usage:
    python -m agents.run_agent --agent quality
    python -m agents.run_agent --agent security --config config.json
"""

import argparse
import asyncio
import sys
from pathlib import Path


def main():
    """Main entry point for agent runner."""
    parser = argparse.ArgumentParser(description="Run autonomous collector agent")
    parser.add_argument(
        "--agent",
        required=True,
        choices=["quality", "security", "flow", "deployment", "collaboration", "risk", "ownership"],
        help="Agent type to run",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Optional path to config file (JSON)",
    )

    args = parser.parse_args()

    # Load config if provided
    config = None
    if args.config:
        import json

        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}")
            sys.exit(1)

        config = json.loads(config_path.read_text())

    # Import and run agent
    if args.agent == "quality":
        from agents.collectors.quality_agent import QualityAgent

        agent = QualityAgent(config=config)
    elif args.agent == "security":
        print(f"Error: {args.agent} agent not yet implemented")
        sys.exit(1)
    elif args.agent == "flow":
        print(f"Error: {args.agent} agent not yet implemented")
        sys.exit(1)
    elif args.agent == "deployment":
        print(f"Error: {args.agent} agent not yet implemented")
        sys.exit(1)
    elif args.agent == "collaboration":
        print(f"Error: {args.agent} agent not yet implemented")
        sys.exit(1)
    elif args.agent == "risk":
        print(f"Error: {args.agent} agent not yet implemented")
        sys.exit(1)
    elif args.agent == "ownership":
        print(f"Error: {args.agent} agent not yet implemented")
        sys.exit(1)
    else:
        print(f"Error: Unknown agent: {args.agent}")
        sys.exit(1)

    # Run agent
    print(f"Engineering Observatory - {args.agent.title()} Agent")
    print("=" * 60)

    success = asyncio.run(agent.run())

    if success:
        print(f"\n✅ {args.agent.title()} agent completed successfully")
        sys.exit(0)
    else:
        print(f"\n❌ {args.agent.title()} agent failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
