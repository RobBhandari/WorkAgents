"""
Ask EI Knowledge Base — learned Q&A storage and retrieval.

Two files:
  - ask_ei_log.json:       Raw log of every Gemini Q&A (append-only)
  - ask_ei_knowledge.json: Curated/approved Q&A pairs (used for instant lookup)

Public API:
  - log_qa(query, intent, narrative, source) -> None
  - lookup_knowledge(query) -> str | None
  - get_pending_log_entries() -> list[dict]
  - promote_entries(indices) -> int
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOG_PATH = Path("data/ask_ei_log.json")
_KNOWLEDGE_PATH = Path("data/ask_ei_knowledge.json")


def _read_json(path: Path) -> list[dict[str, Any]]:
    """Read a JSON array file, returning [] if missing or corrupt."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return []


def _write_json(path: Path, data: list[dict[str, Any]]) -> None:
    """Write a JSON array to file, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def log_qa(
    query: str,
    intent: str,
    narrative: str,
    source: str = "gemini",
) -> None:
    """Append a Q&A entry to the raw log file.

    Args:
        query: The user's original question.
        intent: The classified intent key.
        narrative: The generated answer text.
        source: Where the narrative came from ("gemini" or "template").
    """
    entries = _read_json(_LOG_PATH)
    entries.append(
        {
            "query": query,
            "intent": intent,
            "narrative": narrative,
            "source": source,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "promoted": False,
        }
    )
    _write_json(_LOG_PATH, entries)


def lookup_knowledge(query: str) -> str | None:
    """Check the curated knowledge base for a matching answer.

    Uses case-insensitive substring matching against stored keywords.
    Returns the stored narrative if found, None otherwise.

    Args:
        query: The user's question.

    Returns:
        Stored narrative string, or None if no match.
    """
    knowledge = _read_json(_KNOWLEDGE_PATH)
    if not knowledge:
        return None

    lowered = query.lower().strip()

    # Exact query match first (fastest)
    for entry in knowledge:
        if entry.get("query", "").lower().strip() == lowered:
            return entry.get("narrative")  # type: ignore[no-any-return]

    # Keyword match — entry has a "keywords" list, all must appear in query
    for entry in knowledge:
        keywords = entry.get("keywords", [])
        if keywords and all(kw.lower() in lowered for kw in keywords):
            return entry.get("narrative")  # type: ignore[no-any-return]

    return None


def get_pending_log_entries() -> list[dict[str, Any]]:
    """Return log entries that have not yet been promoted to the knowledge base."""
    entries = _read_json(_LOG_PATH)
    return [e for e in entries if not e.get("promoted", False)]


def promote_entries(indices: list[int], keywords_map: dict[int, list[str]] | None = None) -> int:
    """Promote log entries by index into the knowledge base.

    Args:
        indices: List of 0-based indices into the pending entries list.
        keywords_map: Optional dict mapping index -> keyword list for matching.
            If not provided, the query text is used as-is (exact match only).

    Returns:
        Number of entries promoted.
    """
    pending = get_pending_log_entries()
    knowledge = _read_json(_KNOWLEDGE_PATH)
    log_entries = _read_json(_LOG_PATH)
    keywords_map = keywords_map or {}

    promoted_count = 0
    promoted_queries: set[str] = set()

    for idx in sorted(indices):
        if idx < 0 or idx >= len(pending):
            continue
        entry = pending[idx]
        query = entry.get("query", "")
        if query in promoted_queries:
            continue

        knowledge_entry: dict[str, Any] = {
            "query": query,
            "intent": entry.get("intent", ""),
            "narrative": entry.get("narrative", ""),
            "keywords": keywords_map.get(idx, []),
            "promoted_at": datetime.now(tz=UTC).isoformat(),
        }
        knowledge.append(knowledge_entry)
        promoted_queries.add(query)
        promoted_count += 1

    # Mark promoted entries in the log
    pending_idx = 0
    for log_entry in log_entries:
        if log_entry.get("promoted", False):
            continue
        if pending_idx in indices and log_entry.get("query", "") in promoted_queries:
            log_entry["promoted"] = True
        pending_idx += 1

    _write_json(_KNOWLEDGE_PATH, knowledge)
    _write_json(_LOG_PATH, log_entries)
    return promoted_count
