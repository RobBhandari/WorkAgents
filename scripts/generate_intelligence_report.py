#!/usr/bin/env python3
"""
Generate Weekly Strategic Intelligence Report.

Assembles MetricInsight objects from the narrative engine and writes an
executive HTML report to .tmp/observatory/dashboards/ (or a custom path).

Usage:
    python -m scripts.generate_intelligence_report
    python -m scripts.generate_intelligence_report --use-llm
    python -m scripts.generate_intelligence_report --output-dir /custom/path

Exit codes:
    0 — report generated successfully
    1 — unrecoverable error (details logged; no raw stack trace to stdout)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from execution.core.logging_config import get_logger
from execution.intelligence.narrative_engine import generate_report

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_intelligence_report",
        description="Generate the Weekly Strategic Intelligence Report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m scripts.generate_intelligence_report\n"
            "  python -m scripts.generate_intelligence_report --use-llm\n"
            "  python -m scripts.generate_intelligence_report "
            "--output-dir /tmp/reports\n"
        ),
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        default=False,
        help=(
            "Attempt LLM insight generation via Anthropic API. "
            "Requires ANTHROPIC_API_KEY environment variable. "
            "Falls back to template insights if the key is absent or the call fails."
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        default=None,
        help=(
            "Directory where report HTML files will be written. "
            "Defaults to .tmp/observatory/dashboards/. "
            "The directory is created if it does not exist."
        ),
    )
    return parser


def _resolve_output_dir(raw: str | None) -> Path | None:
    """
    Resolve and validate the --output-dir argument.

    Returns None (use default) when raw is None.
    Raises SystemExit with an error message for invalid paths.

    Security: path resolution uses Path.resolve() — no shell=True, no
    subprocess, no user-controlled string interpolation in file operations.
    """
    if raw is None:
        return None

    try:
        resolved = Path(raw).resolve()
    except (ValueError, OSError) as exc:
        # Emit structured error — no raw stack trace
        logger.error(
            "Invalid --output-dir value",
            extra={"raw": raw, "error": str(exc)},
        )
        print(f"ERROR: Invalid output directory '{raw}': {exc}", file=sys.stderr)
        sys.exit(1)

    return resolved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for generate_intelligence_report.

    Args:
        argv: Argument list (default: sys.argv[1:]).

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    output_dir = _resolve_output_dir(args.output_dir)

    logger.info(
        "Starting intelligence report generation",
        extra={"use_llm": args.use_llm, "output_dir": str(output_dir)},
    )

    try:
        html = generate_report(use_llm=args.use_llm, output_dir=output_dir)
    except OSError as exc:
        logger.error(
            "Report generation failed — I/O error",
            extra={"error": str(exc)},
        )
        print(f"ERROR: Report generation failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        # Catch-all at the CLI boundary: log with context, emit clean message,
        # do NOT let a raw traceback reach stdout.
        logger.error(
            "Report generation failed — unexpected error",
            extra={"error": str(exc)},
        )
        print(f"ERROR: Unexpected failure during report generation: {exc}", file=sys.stderr)
        return 1

    # Success — print summary to stdout
    effective_dir = output_dir or Path(".tmp/observatory/dashboards")
    print("Intelligence report generated successfully.")
    print(f"  Output directory : {effective_dir}")
    print(f"  Report size      : {len(html):,} bytes")
    print(f"  Latest URL       : {effective_dir}/intelligence_report_latest.html")

    return 0


if __name__ == "__main__":
    sys.exit(main())
