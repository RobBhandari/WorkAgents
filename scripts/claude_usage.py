"""
Claude Code session usage report.

Counts sessions per project by scanning ~/.claude/projects/ for .jsonl files
(one file = one session). Groups by project and date.

Usage:
    python -m scripts.claude_usage
    python -m scripts.claude_usage --days 7
    python -m scripts.claude_usage --days 90
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path


def _session_start(path: Path) -> datetime | None:
    """Read the session start timestamp from the first line of a JSONL file."""
    try:
        with open(path, encoding="utf-8") as fh:
            first = fh.readline()
        ts_str = json.loads(first).get("timestamp", "")
        if ts_str:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    # Fallback to file mtime if no timestamp in first line
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def run(days: int) -> None:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=days)
    projects_root = Path.home() / ".claude" / "projects"

    if not projects_root.exists():
        print(f"No Claude projects directory found at {projects_root}")
        return

    # project_name -> {date_str -> count}
    data: dict[str, dict[str, int]] = {}

    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir():
            continue
        sessions_by_date: dict[str, int] = defaultdict(int)
        for f in project_dir.iterdir():
            if f.suffix != ".jsonl":
                continue
            ts = _session_start(f)
            if ts is None or ts < cutoff:
                continue
            day = ts.strftime("%Y-%m-%d")
            sessions_by_date[day] += 1
        if sessions_by_date:
            data[project_dir.name] = dict(sessions_by_date)

    if not data:
        print(f"No sessions found in the last {days} days.")
        return

    totals = {project: sum(d.values()) for project, d in data.items()}
    total_all = sum(totals.values())
    today = now.strftime("%Y-%m-%d")

    print(f"\nClaude Code Usage — last {days} days (to {today})")
    print("=" * 60)

    for project, sessions_by_date in sorted(data.items(), key=lambda x: -totals[x[0]]):
        project_total = totals[project]
        # Friendly name: strip leading path separators encoded as '--'
        friendly = project.replace("--", "/").replace("-", " ").strip("/")
        print(f"\n  {friendly}")
        print(f"  {project_total} sessions across {len(sessions_by_date)} active days")
        print()
        for day in sorted(sessions_by_date):
            count = sessions_by_date[day]
            bar = "#" * count
            print(f"    {day}  {count:3d}  {bar}")

    print()
    print("=" * 60)
    print(f"  TOTAL: {total_all} sessions across {len(data)} project(s)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Code session usage report")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    args = parser.parse_args()
    run(args.days)


if __name__ == "__main__":
    main()
