"""
Unit tests for security_content_builder helper functions.

Tests cover the extracted private helpers to verify each builds correct output
in isolation from the full dashboard pipeline.
"""

from __future__ import annotations

import pytest

from execution.collectors.armorcode_vulnerability_loader import VulnerabilityDetail
from execution.dashboards.security_content_builder import (
    _build_bucket_detail_and_categories,
    _build_bucket_no_detail_row,
    _build_bucket_search_bar,
    _build_bucket_table_row,
    _build_bucket_thead,
    _build_category_counts,
    _build_expanded_html,
    _build_product_row,
    _filter_bucket_counts,
    _group_vulns_by_bucket,
    _resolve_bucket_counts,
    _resolve_product_status,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_vuln(severity: str, source: str | None, product: str = "Web Application") -> VulnerabilityDetail:
    """Construct a minimal VulnerabilityDetail for tests."""
    return VulnerabilityDetail(
        id=f"vuln-{severity[:1]}-{source or 'none'}",
        title=f"{severity} finding from {source}",
        description="",
        severity=severity,
        status="OPEN",
        created_at="",
        product=product,
        age_days=30,
        source=source,
    )


@pytest.fixture
def code_vuln() -> VulnerabilityDetail:
    return _make_vuln("CRITICAL", "Mend")


@pytest.fixture
def high_code_vuln() -> VulnerabilityDetail:
    return _make_vuln("HIGH", "SonarQube")


@pytest.fixture
def infra_vuln() -> VulnerabilityDetail:
    return _make_vuln("HIGH", "Cortex XDR")


@pytest.fixture
def mixed_vulns(code_vuln, high_code_vuln, infra_vuln) -> list:
    return [code_vuln, high_code_vuln, infra_vuln]


# ---------------------------------------------------------------------------
# _build_bucket_thead
# ---------------------------------------------------------------------------


class TestBuildBucketThead:
    def test_contains_severity_column(self):
        html = _build_bucket_thead()
        assert "Severity" in html

    def test_contains_source_column(self):
        html = _build_bucket_thead()
        assert "Source" in html

    def test_contains_status_column(self):
        html = _build_bucket_thead()
        assert "Status" in html

    def test_contains_age_column(self):
        html = _build_bucket_thead()
        assert "Age (Days)" in html

    def test_contains_title_column(self):
        html = _build_bucket_thead()
        assert "Title" in html

    def test_contains_id_column(self):
        html = _build_bucket_thead()
        assert "ID" in html

    def test_is_wrapped_in_thead(self):
        html = _build_bucket_thead()
        assert html.startswith("<thead>")
        assert html.endswith("</thead>")

    def test_contains_sortable_class(self):
        html = _build_bucket_thead()
        assert "sortable" in html

    def test_contains_sort_bucket_table_handler(self):
        html = _build_bucket_thead()
        assert "sortBucketTable" in html


# ---------------------------------------------------------------------------
# _build_bucket_search_bar
# ---------------------------------------------------------------------------


class TestBuildBucketSearchBar:
    def test_all_count_matches_total_vulns(self, mixed_vulns):
        html = _build_bucket_search_bar(mixed_vulns)
        assert f"All ({len(mixed_vulns)})" in html

    def test_critical_count_correct(self, code_vuln, high_code_vuln):
        vulns = [code_vuln, high_code_vuln]  # 1 CRITICAL, 1 HIGH
        html = _build_bucket_search_bar(vulns)
        assert "Critical (1)" in html

    def test_high_count_correct(self, code_vuln, high_code_vuln):
        vulns = [code_vuln, high_code_vuln]  # 1 CRITICAL, 1 HIGH
        html = _build_bucket_search_bar(vulns)
        assert "High (1)" in html

    def test_empty_list_shows_zero_counts(self):
        html = _build_bucket_search_bar([])
        assert "All (0)" in html
        assert "Critical (0)" in html
        assert "High (0)" in html

    def test_contains_filter_bar_class(self, mixed_vulns):
        html = _build_bucket_search_bar(mixed_vulns)
        assert "bucket-filter-bar" in html

    def test_contains_search_placeholder(self, mixed_vulns):
        html = _build_bucket_search_bar(mixed_vulns)
        assert "Search vulnerabilities" in html

    def test_multiple_criticals_counted(self):
        vulns = [
            _make_vuln("CRITICAL", "Mend"),
            _make_vuln("CRITICAL", "SonarQube"),
            _make_vuln("HIGH", "Mend"),
        ]
        html = _build_bucket_search_bar(vulns)
        assert "Critical (2)" in html
        assert "High (1)" in html


# ---------------------------------------------------------------------------
# _build_bucket_no_detail_row
# ---------------------------------------------------------------------------


class TestBuildBucketNoDetailRow:
    def test_contains_bucket_name(self):
        html = _build_bucket_no_detail_row("CODE", 50, 10, 40)
        assert "CODE" in html

    def test_contains_total_count(self):
        html = _build_bucket_no_detail_row("CODE", 50, 10, 40)
        assert "50" in html

    def test_contains_unavailable_message(self):
        html = _build_bucket_no_detail_row("INFRASTRUCTURE", 100, 5, 95)
        assert "beyond the 50-result limit" in html

    def test_expandable_class_present(self):
        html = _build_bucket_no_detail_row("CLOUD", 20, 2, 18)
        assert "bucket-row expandable" in html

    def test_critical_class_applied_when_critical_gt_zero(self):
        html = _build_bucket_no_detail_row("CODE", 10, 3, 7)
        assert 'class="critical"' in html

    def test_no_critical_class_when_zero_critical(self):
        html = _build_bucket_no_detail_row("CODE", 5, 0, 5)
        assert 'class="critical"' not in html

    def test_high_class_applied_when_high_gt_zero(self):
        html = _build_bucket_no_detail_row("CODE", 10, 3, 7)
        assert 'class="high"' in html

    def test_no_high_class_when_zero_high(self):
        html = _build_bucket_no_detail_row("CODE", 5, 5, 0)
        assert 'class="high"' not in html

    def test_bucket_name_lowercase_in_data_attribute(self):
        html = _build_bucket_no_detail_row("INFRASTRUCTURE", 10, 1, 9)
        assert 'data-bucket="infrastructure"' in html


# ---------------------------------------------------------------------------
# _build_bucket_table_row
# ---------------------------------------------------------------------------


class TestBuildBucketTableRow:
    def test_contains_severity_badge(self, code_vuln):
        html = _build_bucket_table_row(code_vuln, 0)
        assert "badge-critical" in html

    def test_contains_source(self, code_vuln):
        html = _build_bucket_table_row(code_vuln, 0)
        assert "Mend" in html

    def test_contains_status(self, code_vuln):
        html = _build_bucket_table_row(code_vuln, 0)
        assert "OPEN" in html

    def test_contains_age_days(self, code_vuln):
        html = _build_bucket_table_row(code_vuln, 0)
        assert "30" in html

    def test_contains_vuln_id(self, code_vuln):
        html = _build_bucket_table_row(code_vuln, 0)
        assert code_vuln.id in html

    def test_data_idx_attribute(self, code_vuln):
        html = _build_bucket_table_row(code_vuln, 7)
        assert 'data-idx="7"' in html

    def test_severity_badge_high(self, infra_vuln):
        html = _build_bucket_table_row(infra_vuln, 0)
        assert "badge-high" in html

    def test_html_escaping_in_source(self):
        vuln = _make_vuln("HIGH", "<script>alert(1)</script>")
        html = _build_bucket_table_row(vuln, 0)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_none_source_renders_empty(self):
        vuln = _make_vuln("CRITICAL", None)
        html = _build_bucket_table_row(vuln, 0)
        assert "vuln-source" in html


# ---------------------------------------------------------------------------
# _resolve_bucket_counts
# ---------------------------------------------------------------------------


class TestResolveBucketCounts:
    def test_uses_accurate_counts_when_provided(self):
        bucket_counts = {"CODE": {"total": 100, "critical": 10, "high": 90}}
        total, critical, high = _resolve_bucket_counts("CODE", [], bucket_counts)
        assert total == 100
        assert critical == 10
        assert high == 90

    def test_derives_from_fetched_when_no_accurate(self):
        vulns = [_make_vuln("CRITICAL", "Mend"), _make_vuln("HIGH", "Mend")]
        total, critical, high = _resolve_bucket_counts("CODE", vulns, None)
        assert total == 2
        assert critical == 1
        assert high == 1

    def test_derives_from_fetched_when_bucket_missing_from_accurate(self):
        bucket_counts = {"CLOUD": {"total": 5, "critical": 1, "high": 4}}
        vulns = [_make_vuln("HIGH", "Mend")]
        total, critical, high = _resolve_bucket_counts("CODE", vulns, bucket_counts)
        assert total == 1
        assert critical == 0
        assert high == 1

    def test_empty_vulns_and_no_accurate_returns_zeros(self):
        total, critical, high = _resolve_bucket_counts("CODE", [], None)
        assert total == 0
        assert critical == 0
        assert high == 0


# ---------------------------------------------------------------------------
# _group_vulns_by_bucket
# ---------------------------------------------------------------------------


class TestGroupVulnsByBucket:
    def test_mend_goes_to_code_bucket(self, code_vuln):
        result = _group_vulns_by_bucket([code_vuln])
        assert code_vuln in result["CODE"]

    def test_cortex_xdr_goes_to_infrastructure(self, infra_vuln):
        result = _group_vulns_by_bucket([infra_vuln])
        assert infra_vuln in result["INFRASTRUCTURE"]

    def test_prisma_cloud_goes_to_cloud(self):
        vuln = _make_vuln("HIGH", "Prisma Cloud Redlock")
        result = _group_vulns_by_bucket([vuln])
        assert vuln in result["CLOUD"]

    def test_unknown_source_goes_to_other(self):
        vuln = _make_vuln("HIGH", "UnknownTool")
        result = _group_vulns_by_bucket([vuln])
        assert vuln in result["Other"]

    def test_medium_vulns_excluded(self):
        vuln = _make_vuln("MEDIUM", "Mend")
        result = _group_vulns_by_bucket([vuln])
        assert vuln not in result["CODE"]

    def test_low_vulns_excluded(self):
        vuln = _make_vuln("LOW", "Mend")
        result = _group_vulns_by_bucket([vuln])
        assert vuln not in result["CODE"]

    def test_empty_input_returns_all_empty_buckets(self):
        result = _group_vulns_by_bucket([])
        for bucket_list in result.values():
            assert bucket_list == []


# ---------------------------------------------------------------------------
# _filter_bucket_counts
# ---------------------------------------------------------------------------


class TestFilterBucketCounts:
    def test_filters_to_active_buckets(self):
        counts = {
            "CODE": {"total": 5, "critical": 1, "high": 4},
            "INFRASTRUCTURE": {"total": 3, "critical": 0, "high": 3},
        }
        active = frozenset({"CODE"})
        result = _filter_bucket_counts(counts, active)
        assert "CODE" in result
        assert "INFRASTRUCTURE" not in result

    def test_returns_empty_dict_when_none(self):
        result = _filter_bucket_counts(None, frozenset({"CODE"}))
        assert result == {}

    def test_returns_empty_dict_when_empty(self):
        result = _filter_bucket_counts({}, frozenset({"CODE"}))
        assert result == {}

    def test_all_buckets_pass_when_all_active(self):
        counts = {
            "CODE": {"total": 2, "critical": 1, "high": 1},
            "CLOUD": {"total": 3, "critical": 0, "high": 3},
        }
        active = frozenset({"CODE", "CLOUD"})
        result = _filter_bucket_counts(counts, active)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _resolve_product_status
# ---------------------------------------------------------------------------


class TestResolveProductStatus:
    def test_critical_status_when_five_or_more_critical(self):
        status, css, priority = _resolve_product_status(5, 10)
        assert status == "Critical"
        assert css == "action"
        assert priority == 0

    def test_high_risk_when_one_to_four_critical(self):
        status, css, priority = _resolve_product_status(1, 5)
        assert status == "High Risk"
        assert css == "caution"
        assert priority == 1

    def test_monitor_when_zero_critical_and_ten_plus_high(self):
        status, css, priority = _resolve_product_status(0, 10)
        assert status == "Monitor"
        assert css == "caution"
        assert priority == 2

    def test_ok_when_zero_critical_and_few_high(self):
        status, css, priority = _resolve_product_status(0, 5)
        assert status == "OK"
        assert css == "good"
        assert priority == 3

    def test_ok_when_all_zero(self):
        status, css, priority = _resolve_product_status(0, 0)
        assert status == "OK"
        assert css == "good"
        assert priority == 3

    def test_critical_threshold_is_five(self):
        # 4 critical → High Risk, 5 critical → Critical
        status_4, _, _ = _resolve_product_status(4, 0)
        status_5, _, _ = _resolve_product_status(5, 0)
        assert status_4 == "High Risk"
        assert status_5 == "Critical"


# ---------------------------------------------------------------------------
# _build_bucket_detail_and_categories
# ---------------------------------------------------------------------------


class TestBuildBucketDetailAndCategories:
    def test_returns_all_three_buckets_in_detail(self):
        bucket_detail, _ = _build_bucket_detail_and_categories(None, frozenset())
        assert "code" in bucket_detail
        assert "cloud" in bucket_detail
        assert "infrastructure" in bucket_detail

    def test_detail_zeroed_when_no_counts(self):
        bucket_detail, _ = _build_bucket_detail_and_categories(None, frozenset())
        assert bucket_detail["code"] == {"critical": 0, "high": 0}

    def test_detail_populated_from_counts(self):
        counts = {"CODE": {"critical": 3, "high": 7, "total": 10}}
        bucket_detail, _ = _build_bucket_detail_and_categories(counts, frozenset({"CODE"}))
        assert bucket_detail["code"]["critical"] == 3
        assert bucket_detail["code"]["high"] == 7

    def test_category_included_when_active_and_has_total(self):
        counts = {"CODE": {"critical": 1, "high": 2, "total": 3}}
        _, categories = _build_bucket_detail_and_categories(counts, frozenset({"CODE"}))
        assert "code" in categories

    def test_category_excluded_when_total_is_zero(self):
        counts = {"CODE": {"critical": 0, "high": 0, "total": 0}}
        _, categories = _build_bucket_detail_and_categories(counts, frozenset({"CODE"}))
        assert "code" not in categories

    def test_category_excluded_when_bucket_not_active(self):
        counts = {"CODE": {"critical": 1, "high": 2, "total": 3}}
        _, categories = _build_bucket_detail_and_categories(counts, frozenset({"CLOUD"}))
        assert "code" not in categories

    def test_multiple_active_categories(self):
        counts = {
            "CODE": {"critical": 1, "high": 2, "total": 3},
            "CLOUD": {"critical": 0, "high": 5, "total": 5},
        }
        _, categories = _build_bucket_detail_and_categories(counts, frozenset({"CODE", "CLOUD"}))
        assert "code" in categories
        assert "cloud" in categories


# ---------------------------------------------------------------------------
# _build_category_counts
# ---------------------------------------------------------------------------


class TestBuildCategoryCounts:
    def test_code_total_summed_across_products(self):
        bucket_counts = {
            "Alpha": {"CODE": {"total": 5, "critical": 1, "high": 4}},
            "Beta": {"CODE": {"total": 3, "critical": 0, "high": 3}},
        }
        result = _build_category_counts(frozenset({"CODE"}), bucket_counts)
        assert result["code"] == 8

    def test_cloud_total_summed_across_products(self):
        bucket_counts = {
            "Alpha": {"CLOUD": {"total": 10, "critical": 2, "high": 8}},
            "Beta": {"CLOUD": {"total": 4, "critical": 1, "high": 3}},
        }
        result = _build_category_counts(frozenset({"CLOUD"}), bucket_counts)
        assert result["cloud"] == 14

    def test_infrastructure_total_summed(self):
        bucket_counts = {
            "Alpha": {"INFRASTRUCTURE": {"total": 7, "critical": 0, "high": 7}},
        }
        result = _build_category_counts(frozenset({"INFRASTRUCTURE"}), bucket_counts)
        assert result["infrastructure"] == 7

    def test_inactive_bucket_not_in_result(self):
        bucket_counts = {
            "Alpha": {"CODE": {"total": 5, "critical": 1, "high": 4}},
        }
        result = _build_category_counts(frozenset({"CLOUD"}), bucket_counts)
        assert "code" not in result

    def test_empty_bucket_counts_returns_zero(self):
        result = _build_category_counts(frozenset({"CODE"}), {})
        assert result["code"] == 0

    def test_missing_bucket_for_product_treated_as_zero(self):
        bucket_counts = {
            "Alpha": {},  # no CODE key
            "Beta": {"CODE": {"total": 3, "critical": 0, "high": 3}},
        }
        result = _build_category_counts(frozenset({"CODE"}), bucket_counts)
        assert result["code"] == 3


# ---------------------------------------------------------------------------
# _build_product_row
# ---------------------------------------------------------------------------


class TestBuildProductRow:
    """Tests for _build_product_row — verifies correct status, counts, and structure."""

    class _FakeMetrics:
        medium = 5

    def test_critical_status_set_correctly(self):
        counts = {"CODE": {"total": 5, "critical": 5, "high": 0}}
        row = _build_product_row(
            "Product A",
            self._FakeMetrics(),
            [],
            counts,
            frozenset({"CODE"}),
            set(),
        )
        assert row["status"] == "Critical"
        assert row["status_class"] == "action"

    def test_ok_status_when_no_critical_or_high(self):
        row = _build_product_row(
            "Clean Product",
            self._FakeMetrics(),
            [],
            None,
            frozenset({"CODE"}),
            set(),
        )
        assert row["status"] == "OK"
        assert row["status_class"] == "good"

    def test_product_name_in_row(self):
        row = _build_product_row(
            "My Product",
            self._FakeMetrics(),
            [],
            None,
            frozenset({"CODE"}),
            set(),
        )
        assert row["name"] == "My Product"

    def test_medium_comes_from_metrics(self):
        row = _build_product_row(
            "Product",
            self._FakeMetrics(),
            [],
            None,
            frozenset({"CODE"}),
            set(),
        )
        assert row["medium"] == 5

    def test_totals_summed_from_filtered_buckets(self):
        counts = {"CODE": {"total": 3, "critical": 2, "high": 1}}
        row = _build_product_row(
            "P",
            self._FakeMetrics(),
            [],
            counts,
            frozenset({"CODE"}),
            set(),
        )
        assert row["critical"] == 2
        assert row["high"] == 1
        assert row["total"] == 3

    def test_inactive_bucket_counts_excluded(self):
        counts = {
            "CODE": {"total": 10, "critical": 5, "high": 5},
            "INFRASTRUCTURE": {"total": 20, "critical": 10, "high": 10},
        }
        # Only CODE is active
        row = _build_product_row(
            "P",
            self._FakeMetrics(),
            [],
            counts,
            frozenset({"CODE"}),
            set(),
        )
        assert row["critical"] == 5
        assert row["high"] == 5

    def test_expanded_html_is_string(self):
        row = _build_product_row(
            "P",
            self._FakeMetrics(),
            [],
            None,
            frozenset({"CODE"}),
            set(),
        )
        assert isinstance(row["expanded_html"], str)

    def test_bucket_detail_keys_present(self):
        row = _build_product_row(
            "P",
            self._FakeMetrics(),
            [],
            None,
            frozenset({"CODE"}),
            set(),
        )
        assert "code" in row["bucket_detail"]
        assert "cloud" in row["bucket_detail"]
        assert "infrastructure" in row["bucket_detail"]


# ---------------------------------------------------------------------------
# _build_expanded_html
# ---------------------------------------------------------------------------


class TestBuildExpandedHtml:
    def test_filters_vulns_to_active_sources(self):
        code_vuln = _make_vuln("CRITICAL", "Mend")
        infra_vuln = _make_vuln("HIGH", "Cortex XDR")
        # Only Mend is in active source names
        html = _build_expanded_html([code_vuln, infra_vuln], {"Mend"}, {})
        assert "CODE" in html
        assert "INFRASTRUCTURE" not in html

    def test_passes_bucket_counts_when_present(self):
        counts = {"CODE": {"total": 999, "critical": 5, "high": 994}}
        html = _build_expanded_html([], {"Mend"}, counts)
        assert "999" in html

    def test_returns_no_findings_when_empty_and_no_counts(self):
        html = _build_expanded_html([], set(), {})
        assert "No Critical or High findings" in html
