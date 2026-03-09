"""
Claude Code session usage report.

Counts sessions per project by scanning ~/.claude/projects/ for .jsonl files
(one file = one session). Groups by project and date.

Usage:
    python -m scripts.claude_usage
    python -m scripts.claude_usage --days 7
    python -m scripts.claude_usage --days 90
    python -m scripts.claude_usage --html
"""

import argparse
import html as html_lib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _friendly(project_dir_name: str) -> str:
    return project_dir_name.replace("--", "/").replace("-", " ").strip("/")


def _session_start(path: Path) -> datetime | None:
    """Return session start timestamp only for real conversation sessions.

    Filters to queue-operation files (actual sessions), skipping file-history-snapshot,
    system, and other metadata files that share the .jsonl extension.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            first = fh.readline()
        data = json.loads(first)
        if data.get("type") != "queue-operation":
            return None
        ts_str = data.get("timestamp", "")
        if ts_str:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    # Fallback to file mtime if no timestamp in first line
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _parse_session(path: Path, cutoff: datetime) -> dict | None:
    """Parse a session JSONL into a rich dict. Returns None if outside cutoff."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    if not lines:
        return None

    first = json.loads(lines[0])
    if first.get("type") != "queue-operation":
        return None
    ts_str = first.get("timestamp", "")
    if not ts_str:
        return None
    start = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if start < cutoff:
        return None

    turns = 0
    total_tokens = 0
    model = ""
    branch = ""
    first_user_msg = ""
    # Track all timestamps to detect background compaction writing after session ends.
    # We use the last timestamp before any gap >2h as the real session end time.
    all_ts: list[datetime] = [start]

    for raw in lines[1:]:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        t = entry.get("type", "")
        if not branch and entry.get("gitBranch"):
            branch = entry["gitBranch"]
        entry_ts = entry.get("timestamp", "")
        if entry_ts:
            try:
                all_ts.append(datetime.fromisoformat(entry_ts.replace("Z", "+00:00")))
            except ValueError:
                pass
        if t == "user":
            turns += 1
            if not first_user_msg:
                msg = entry.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        first_user_msg = content[:120]
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                first_user_msg = block.get("text", "")[:120]
                                break
        elif t == "assistant":
            msg = entry.get("message", {})
            if isinstance(msg, dict):
                if not model and msg.get("model"):
                    model = msg["model"].replace("claude-", "").replace("-20", " 20")
                usage = msg.get("usage", {})
                if isinstance(usage, dict):
                    total_tokens += (
                        usage.get("input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                        + usage.get("output_tokens", 0)
                    )

    # Find real end: last timestamp before a gap >2h (filters background compaction)
    gap_seconds = 7200  # 2 hours in seconds
    end_ts = start
    for i in range(len(all_ts) - 1):
        end_ts = all_ts[i]
        if (all_ts[i + 1] - all_ts[i]).total_seconds() > gap_seconds:
            break
    else:
        end_ts = all_ts[-1]
    duration_min = max(0, int((end_ts - start).total_seconds() / 60))
    return {
        "session_id": path.stem,
        "start": start,
        "duration_min": duration_min,
        "model": model,
        "turns": turns,
        "total_tokens": total_tokens,
        "branch": branch,
        "first_user_msg": first_user_msg,
        "project_dir": path.parent.name,
    }


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

    print(f"\nClaude Code Usage \u2014 last {days} days (to {today})")
    print("=" * 60)

    for project, sessions_by_date in sorted(data.items(), key=lambda x: -totals[x[0]]):
        project_total = totals[project]
        friendly = _friendly(project)
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


def run_html(days: int, out_path: Path) -> None:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=days)
    projects_root = Path.home() / ".claude" / "projects"

    if not projects_root.exists():
        print(f"No Claude projects directory found at {projects_root}")
        return

    # Collect all sessions, grouped by date
    sessions_by_date: dict[str, list[dict]] = defaultdict(list)
    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir():
            continue
        for f in project_dir.iterdir():
            if f.suffix != ".jsonl":
                continue
            s = _parse_session(f, cutoff)
            if s:
                day = s["start"].strftime("%Y-%m-%d")
                sessions_by_date[day].append(s)

    if not sessions_by_date:
        print(f"No sessions found in the last {days} days.")
        return

    total_sessions = sum(len(v) for v in sessions_by_date.values())
    active_days = len(sessions_by_date)
    total_tokens = sum(s["total_tokens"] for ss in sessions_by_date.values() for s in ss)
    today = now.strftime("%Y-%m-%d")

    # Build CSV data for download
    csv_rows = ["Session ID,Date,Start,Duration (min),Model,Turns,Tokens,Branch,Project,First Message"]
    for day in sorted(sessions_by_date, reverse=True):
        for s in sorted(sessions_by_date[day], key=lambda x: x["start"]):
            msg = s["first_user_msg"].replace('"', '""')
            csv_rows.append(
                f'{s["session_id"]},{day},{s["start"].strftime("%H:%M:%S")},'
                f'{s["duration_min"]},{s["model"]},{s["turns"]},{s["total_tokens"]},'
                f'{s["branch"]},{_friendly(s["project_dir"])},"{msg}"'
            )
    csv_data = "\n".join(csv_rows)

    # Build day blocks HTML
    day_blocks = []
    for day in sorted(sessions_by_date, reverse=True):
        sessions = sorted(sessions_by_date[day], key=lambda x: x["start"])
        day_total_min = sum(s["duration_min"] for s in sessions)
        day_total_turns = sum(s["turns"] for s in sessions)
        rows = []
        for s in sessions:
            fmsg = html_lib.escape(s["first_user_msg"])
            rows.append(f"""
                <tr>
                  <td class="mono">{s["session_id"]}</td>
                  <td>{s["start"].strftime("%H:%M:%S")}</td>
                  <td>{s["duration_min"] // 60}h {s["duration_min"] % 60:02d}m</td>
                  <td>{html_lib.escape(s["model"])}</td>
                  <td>{s["turns"]}</td>
                  <td>{s["total_tokens"]:,}</td>
                  <td>{html_lib.escape(s["branch"])}</td>
                  <td class="proj-cell">{html_lib.escape(_friendly(s["project_dir"]))}</td>
                </tr>
                <tr class="first-msg-row">
                  <td colspan="8" class="first-msg">{fmsg}</td>
                </tr>""")
        rows_html = "".join(rows)
        day_blocks.append(f"""
          <details class="day-group">
            <summary>
              <span class="day-date">{day}</span>
              <span class="day-sessions">{len(sessions)} session(s)</span>
              <span class="day-total">{day_total_min // 60}h {day_total_min % 60:02d}m</span>
              <span class="day-total">{day_total_turns} turns</span>
            </summary>
            <table>
              <thead>
                <tr>
                  <th>Session ID</th>
                  <th>Start (UTC)</th>
                  <th>Duration</th>
                  <th>Model</th>
                  <th>Turns</th>
                  <th>Tokens</th>
                  <th>Branch</th>
                  <th>Project</th>
                </tr>
              </thead>
              <tbody>{rows_html}
              </tbody>
            </table>
          </details>""")

    day_blocks_html = "\n".join(day_blocks)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Claude Code Usage &mdash; last {days} days</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
  h1 {{ font-size: 1.4rem; font-weight: 600; color: #f1f5f9; margin-bottom: 4px; }}
  .subtitle {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 24px; }}
  .totals {{ display: flex; gap: 24px; margin-bottom: 28px; }}
  .stat {{ background: #1e293b; border-radius: 8px; padding: 14px 20px; }}
  .stat-value {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
  .stat-label {{ font-size: 0.75rem; color: #64748b; margin-top: 2px; }}
  .dl-btn {{ margin-left: auto; align-self: center; background: #38bdf8; border: none; color: #0f172a;
             font-size: 0.85rem; font-weight: 700; padding: 10px 22px; border-radius: 6px; cursor: pointer;
             letter-spacing: 0.02em; }}
  .dl-btn:hover {{ background: #7dd3fc; }}
  details.day-group {{ background: #1e293b; border-radius: 8px; margin-bottom: 6px; overflow: hidden; }}
  details.day-group > summary {{
    display: flex; align-items: center; gap: 0; padding: 14px 20px;
    cursor: pointer; user-select: none; list-style: none;
  }}
  details.day-group > summary::-webkit-details-marker {{ display: none; }}
  details.day-group > summary::before {{
    content: "\\25B6"; font-size: 0.7rem; color: #475569; transition: transform 0.15s;
    min-width: 12px;
  }}
  details.day-group[open] > summary::before {{ transform: rotate(90deg); }}
  .day-date {{ font-weight: 700; color: #f1f5f9; font-size: 1.1rem; min-width: 130px; }}
  .day-sessions {{ font-size: 1rem; font-weight: 600; color: #34d399; min-width: 110px; text-align: right; }}
  .day-total {{ font-size: 1rem; color: #94a3b8; min-width: 90px; text-align: right; font-variant-numeric: tabular-nums; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  thead tr {{ background: #0f172a; }}
  th {{ padding: 8px 12px; text-align: left; color: #64748b; font-weight: 500; font-size: 0.75rem;
        text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; }}
  td {{ padding: 7px 12px; border-top: 1px solid #0f172a; color: #cbd5e1; vertical-align: top; }}
  tr:hover td {{ background: #243044; }}
  .mono {{ font-family: monospace; font-size: 0.78rem; color: #7dd3fc; }}
  .proj-cell {{ color: #64748b; font-size: 0.75rem; }}
  .first-msg {{ color: #64748b; font-size: 0.75rem; font-style: italic; padding-top: 0 !important; padding-bottom: 8px !important; border-top: none !important; }}
  .first-msg-row {{ pointer-events: none; }}
</style>
</head>
<body>
<h1>Claude Code Usage</h1>
<p class="subtitle">Last {days} days &mdash; generated {today}</p>
<div class="totals">
  <div class="stat"><div class="stat-value">{total_sessions:,}</div><div class="stat-label">Total Sessions</div></div>
  <div class="stat"><div class="stat-value">{active_days}</div><div class="stat-label">Active Days</div></div>
  <div class="stat"><div class="stat-value">{total_tokens:,}</div><div class="stat-label">Total Tokens</div></div>
  <button class="dl-btn" onclick="downloadCSV()">Download</button>
</div>
{day_blocks_html}
<script>
const CSV = {json.dumps(csv_data)};
function downloadCSV() {{
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(CSV);
  a.download = 'claude_usage.csv';
  a.click();
}}
</script>
</body>
</html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"HTML report written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Code session usage report")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report to .tmp/claude_usage.html",
    )
    args = parser.parse_args()
    if args.html:
        out = Path(__file__).parent.parent / ".tmp" / "claude_usage.html"
        run_html(args.days, out)
    else:
        run(args.days)


if __name__ == "__main__":
    main()
