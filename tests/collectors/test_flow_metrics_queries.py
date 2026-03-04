"""
Tests for execution/collectors/flow_metrics_queries.py

Covers the extracted helpers and the public query functions at a unit level
using mocked ADO REST client and transformer responses.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from execution.collectors.flow_metrics_queries import (
    _apply_security_bug_filter,
    _build_area_filter_clause,
    _fetch_work_items_batched,
    query_work_items_by_type,
)

# ---------------------------------------------------------------------------
# _build_area_filter_clause
# ---------------------------------------------------------------------------


def test_build_area_filter_clause_none():
    """Returns empty string when no filter is provided."""
    assert _build_area_filter_clause(None) == ""


def test_build_area_filter_clause_empty_string():
    """Returns empty string for empty string input."""
    assert _build_area_filter_clause("") == ""


def test_build_area_filter_clause_exclude():
    """Builds NOT UNDER clause for EXCLUDE prefix."""
    result = _build_area_filter_clause("EXCLUDE:MyProject\\TeamA")
    assert "NOT UNDER" in result
    assert "System.AreaPath" in result


def test_build_area_filter_clause_include():
    """Builds UNDER clause for INCLUDE prefix."""
    result = _build_area_filter_clause("INCLUDE:MyProject\\TeamA")
    assert "NOT UNDER" not in result
    assert "UNDER" in result
    assert "System.AreaPath" in result


def test_build_area_filter_clause_unknown_prefix():
    """Returns empty string for unrecognised prefix."""
    assert _build_area_filter_clause("SOMETHING:path") == ""


# ---------------------------------------------------------------------------
# _apply_security_bug_filter
# ---------------------------------------------------------------------------


def _make_item(title: str = "item") -> dict:
    return {"System.Title": title, "System.CreatedBy": {"displayName": "developer"}}


def _make_armorcode_item(title: str = "sec bug") -> dict:
    return {"System.Title": title, "System.CreatedBy": {"displayName": "ArmorCode"}}


def test_apply_security_bug_filter_non_bug_type():
    """No filtering is applied for non-Bug work types."""
    open_items = [_make_item(), _make_armorcode_item()]
    closed_items = [_make_armorcode_item()]
    out_open, out_closed, ex_open, ex_closed = _apply_security_bug_filter("User Story", open_items, closed_items)
    assert out_open is open_items
    assert out_closed is closed_items
    assert ex_open == 0
    assert ex_closed == 0


def test_apply_security_bug_filter_bug_type_no_security_bugs():
    """Returns unchanged lists with zero excluded counts when no ArmorCode bugs exist."""
    open_items = [_make_item("story 1"), _make_item("story 2")]
    closed_items = [_make_item("story 3")]
    out_open, out_closed, ex_open, ex_closed = _apply_security_bug_filter("Bug", open_items, closed_items)
    assert ex_open == 0
    assert ex_closed == 0
    assert len(out_open) == 2
    assert len(out_closed) == 1


def test_apply_security_bug_filter_bug_type_with_security_bugs():
    """Filters ArmorCode-created bugs and returns correct exclusion counts."""
    open_items = [_make_item("real bug"), _make_armorcode_item()]
    closed_items = [_make_armorcode_item(), _make_armorcode_item()]
    out_open, out_closed, ex_open, ex_closed = _apply_security_bug_filter("Bug", open_items, closed_items)
    assert ex_open == 1
    assert ex_closed == 2
    assert len(out_open) == 1
    assert len(out_closed) == 0


# ---------------------------------------------------------------------------
# _fetch_work_items_batched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_work_items_batched_empty_ids():
    """Returns empty list immediately when no IDs are provided."""
    rest_client = MagicMock()
    result = await _fetch_work_items_batched(
        rest_client,
        item_ids=[],
        fields=["System.Id"],
        work_type="Bug",
        label="open",
    )
    assert result == []
    rest_client.get_work_items.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_work_items_batched_single_batch():
    """Fetches and transforms items when count fits within one batch."""
    fake_item = {"id": 1, "fields": {"System.Title": "Bug 1"}}
    fake_response = MagicMock()

    rest_client = MagicMock()
    rest_client.get_work_items = AsyncMock(return_value=fake_response)

    with patch(
        "execution.collectors.flow_metrics_queries.WorkItemTransformer.transform_work_items_response",
        return_value=[fake_item],
    ):
        result = await _fetch_work_items_batched(
            rest_client,
            item_ids=[1, 2, 3],
            fields=["System.Id", "System.Title"],
            work_type="Bug",
            label="open",
        )

    assert result == [fake_item]
    rest_client.get_work_items.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_work_items_batched_multiple_batches():
    """Splits IDs into 200-item batches and combines results."""
    fake_item = {"id": 1}
    fake_response = MagicMock()

    rest_client = MagicMock()
    rest_client.get_work_items = AsyncMock(return_value=fake_response)

    # 201 IDs should result in 2 batch calls
    ids = list(range(1, 202))

    with patch(
        "execution.collectors.flow_metrics_queries.WorkItemTransformer.transform_work_items_response",
        return_value=[fake_item],
    ):
        result = await _fetch_work_items_batched(
            rest_client,
            item_ids=ids,
            fields=["System.Id"],
            work_type="Task",
            label="open",
        )

    assert rest_client.get_work_items.call_count == 2
    # Two batches each returning [fake_item] → 2 items total
    assert len(result) == 2


@pytest.mark.asyncio
async def test_fetch_work_items_batched_api_error_returns_empty():
    """Returns empty list and logs warning when API call raises an exception."""
    rest_client = MagicMock()
    rest_client.get_work_items = AsyncMock(side_effect=RuntimeError("API error"))

    result = await _fetch_work_items_batched(
        rest_client,
        item_ids=[1, 2],
        fields=["System.Id"],
        work_type="Bug",
        label="open",
    )

    assert result == []


# ---------------------------------------------------------------------------
# query_work_items_by_type — integration-style unit test
# ---------------------------------------------------------------------------


def _make_wiql_item(item_id: int) -> MagicMock:
    m = MagicMock()
    m.id = item_id
    return m


@pytest.mark.asyncio
async def test_query_work_items_by_type_returns_correct_structure():
    """Return dict has all expected keys with correct types."""
    rest_client = MagicMock()

    open_wiql_response = MagicMock()
    closed_wiql_response = MagicMock()

    open_wiql_obj = MagicMock()
    open_wiql_obj.work_items = [_make_wiql_item(1)]
    closed_wiql_obj = MagicMock()
    closed_wiql_obj.work_items = [_make_wiql_item(2)]

    fake_open_item = {"id": 1, "fields": {}}
    fake_closed_item = {"id": 2, "fields": {}}

    rest_client.query_by_wiql = AsyncMock(side_effect=[open_wiql_response, closed_wiql_response])
    rest_client.get_work_items = AsyncMock(return_value=MagicMock())

    with (
        patch(
            "execution.collectors.flow_metrics_queries.WorkItemTransformer.transform_wiql_response",
            side_effect=[open_wiql_obj, closed_wiql_obj],
        ),
        patch(
            "execution.collectors.flow_metrics_queries.WorkItemTransformer.transform_work_items_response",
            side_effect=[[fake_open_item], [fake_closed_item]],
        ),
    ):
        result = await query_work_items_by_type(rest_client, "MyProject", "Task")

    assert result["work_type"] == "Task"
    assert isinstance(result["open_items"], list)
    assert isinstance(result["closed_items"], list)
    assert result["open_count"] == len(result["open_items"])
    assert result["closed_count"] == len(result["closed_items"])
    assert "excluded_security_bugs" in result


@pytest.mark.asyncio
async def test_query_work_items_by_type_error_returns_safe_default():
    """Returns safe default dict when the ADO API raises an exception."""
    rest_client = MagicMock()
    rest_client.query_by_wiql = AsyncMock(side_effect=RuntimeError("network error"))

    result = await query_work_items_by_type(rest_client, "MyProject", "Bug")

    assert result["work_type"] == "Bug"
    assert result["open_items"] == []
    assert result["closed_items"] == []
    assert result["open_count"] == 0
    assert result["closed_count"] == 0


@pytest.mark.asyncio
async def test_query_work_items_by_type_empty_wiql_results():
    """Handles empty WIQL results without making get_work_items calls."""
    rest_client = MagicMock()

    open_wiql_obj = MagicMock()
    open_wiql_obj.work_items = []
    closed_wiql_obj = MagicMock()
    closed_wiql_obj.work_items = []

    rest_client.query_by_wiql = AsyncMock(return_value=MagicMock())
    rest_client.get_work_items = AsyncMock()

    with patch(
        "execution.collectors.flow_metrics_queries.WorkItemTransformer.transform_wiql_response",
        side_effect=[open_wiql_obj, closed_wiql_obj],
    ):
        result = await query_work_items_by_type(rest_client, "MyProject", "User Story")

    rest_client.get_work_items.assert_not_called()
    assert result["open_count"] == 0
    assert result["closed_count"] == 0
