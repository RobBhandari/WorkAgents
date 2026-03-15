"""Tests for execution.intelligence.knowledge_base — Ask EI Q&A storage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.intelligence.knowledge_base import (
    get_pending_log_entries,
    log_qa,
    lookup_knowledge,
    promote_entries,
)


@pytest.fixture(autouse=True)
def _tmp_paths(tmp_path: Path) -> None:  # type: ignore[misc]
    """Redirect log and knowledge paths to temp directory for all tests."""
    log_path = tmp_path / "ask_ei_log.json"
    kb_path = tmp_path / "ask_ei_knowledge.json"
    with (
        patch("execution.intelligence.knowledge_base._LOG_PATH", log_path),
        patch("execution.intelligence.knowledge_base._KNOWLEDGE_PATH", kb_path),
    ):
        yield


class TestLogQA:
    def test_creates_log_file(self, tmp_path: Path) -> None:
        log_qa("test query", "risk_explanation", "test answer", "gemini")
        # Should not raise — file is created automatically

    def test_appends_entries(self) -> None:
        log_qa("q1", "risk_explanation", "a1", "gemini")
        log_qa("q2", "portfolio_summary", "a2", "template")
        pending = get_pending_log_entries()
        assert len(pending) == 2
        assert pending[0]["query"] == "q1"
        assert pending[1]["query"] == "q2"

    def test_entry_has_required_fields(self) -> None:
        log_qa("my query", "trend_drill", "my answer", "gemini")
        entries = get_pending_log_entries()
        entry = entries[0]
        assert entry["query"] == "my query"
        assert entry["intent"] == "trend_drill"
        assert entry["narrative"] == "my answer"
        assert entry["source"] == "gemini"
        assert entry["promoted"] is False
        assert "timestamp" in entry


class TestLookupKnowledge:
    def test_returns_none_when_empty(self) -> None:
        assert lookup_knowledge("anything") is None

    def test_exact_match(self, tmp_path: Path) -> None:
        # Seed the knowledge base via promote
        log_qa("why is risk high?", "risk_explanation", "Risk is at 74.", "gemini")
        promote_entries([0])
        assert lookup_knowledge("why is risk high?") == "Risk is at 74."

    def test_exact_match_case_insensitive(self) -> None:
        log_qa("Why Is Risk High?", "risk_explanation", "Risk is at 74.", "gemini")
        promote_entries([0])
        assert lookup_knowledge("why is risk high?") == "Risk is at 74."

    def test_keyword_match(self) -> None:
        log_qa("test q", "risk_explanation", "keyword answer", "gemini")
        promote_entries([0], keywords_map={0: ["risk", "high"]})
        assert lookup_knowledge("tell me why risk is so high") == "keyword answer"

    def test_keyword_match_requires_all(self) -> None:
        log_qa("test q", "risk_explanation", "keyword answer", "gemini")
        promote_entries([0], keywords_map={0: ["risk", "deployment"]})
        # Only "risk" present, not "deployment"
        assert lookup_knowledge("why is risk high?") is None

    def test_no_match(self) -> None:
        log_qa("specific question", "risk_explanation", "specific answer", "gemini")
        promote_entries([0])
        assert lookup_knowledge("completely different query") is None


class TestPromoteEntries:
    def test_promotes_by_index(self) -> None:
        log_qa("q1", "intent1", "a1", "gemini")
        log_qa("q2", "intent2", "a2", "gemini")
        log_qa("q3", "intent3", "a3", "gemini")
        count = promote_entries([0, 2])
        assert count == 2
        # q1 and q3 promoted, q2 still pending
        pending = get_pending_log_entries()
        assert len(pending) == 1
        assert pending[0]["query"] == "q2"

    def test_ignores_invalid_indices(self) -> None:
        log_qa("q1", "intent1", "a1", "gemini")
        count = promote_entries([0, 5, -1, 99])
        assert count == 1

    def test_returns_zero_for_empty(self) -> None:
        count = promote_entries([0, 1])
        assert count == 0

    def test_promoted_entries_visible_in_knowledge(self) -> None:
        log_qa("my question", "portfolio_summary", "my answer", "gemini")
        promote_entries([0])
        result = lookup_knowledge("my question")
        assert result == "my answer"
