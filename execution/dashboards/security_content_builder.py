"""
Security Dashboard Content Builder

HTML context and content-building functions extracted from security_enhanced.py
to keep it under the 500-line architectural limit.

Contains: template context builder, bucket expanded content, HTML escaping.
"""

from __future__ import annotations

from execution.collectors.armorcode_vulnerability_loader import VulnerabilityDetail
from execution.dashboards.components.cards import summary_card
from execution.dashboards.renderer import render_dashboard
from execution.dashboards.security_helpers import BUCKET_SOURCE_MAP, _calculate_summary
from execution.domain.security import BUCKET_ORDER, SOURCE_BUCKET_MAP
from execution.framework import get_dashboard_framework

# Bucket groupings for mode-based filtering
_CODE_CLOUD_BUCKETS: frozenset[str] = frozenset({"CODE", "CLOUD"})
_INFRA_BUCKETS: frozenset[str] = frozenset({"INFRASTRUCTURE"})


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _generate_bucket_expanded_content(
    vulnerabilities: list,
    bucket_counts: dict | None = None,
) -> str:
    """
    Generate expanded row HTML: inline expandable bucket rows within a single table.

    Args:
        vulnerabilities: List of VulnerabilityDetail objects for this product (max 50/bucket)
        bucket_counts: Production-only {bucket: {total, critical, high}} from API count queries.
                      When None, counts are derived from the fetched vulnerabilities list.
    """
    filtered = [v for v in vulnerabilities if v.severity.upper() in ("CRITICAL", "HIGH")]

    # Group fetched vulns by bucket
    fetched_buckets: dict[str, list] = {b: [] for b in BUCKET_ORDER}
    for vuln in filtered:
        fetched_buckets[SOURCE_BUCKET_MAP.get(vuln.source or "", "Other")].append(vuln)

    # Determine which buckets are active: from accurate counts if available, else from fetched
    active_buckets = set(bucket_counts.keys()) if bucket_counts else {b for b, v in fetched_buckets.items() if v}

    thead = (
        "<thead><tr>"
        '<th class="sortable" onclick="sortBucketTable(this)">Severity <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">Source <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">Status <span class="sort-indicator"></span></th>'
        '<th class="sortable" data-type="number" onclick="sortBucketTable(this)">Age (Days) <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">Title <span class="sort-indicator"></span></th>'
        '<th class="sortable" onclick="sortBucketTable(this)">ID <span class="sort-indicator"></span></th>'
        "</tr></thead>"
    )

    table_body = ""
    for bucket_name in BUCKET_ORDER:
        if bucket_name not in active_buckets:
            continue

        vulns = fetched_buckets[bucket_name]
        fetched_count = len(vulns)

        # Use accurate counts if provided, else derive from fetched
        if bucket_counts and bucket_name in bucket_counts:
            acc = bucket_counts[bucket_name]
            total, critical, high = acc["total"], acc["critical"], acc["high"]
        else:
            total = fetched_count
            critical = sum(1 for v in vulns if v.severity.upper() == "CRITICAL")
            high = total - critical

        crit_cls = ' class="critical"' if critical > 0 else ""
        high_cls = ' class="high"' if high > 0 else ""

        # No fetched detail for this bucket (truncated beyond 50-record limit)
        if fetched_count == 0:
            table_body += (
                f'<tr class="bucket-row expandable" data-bucket="{bucket_name.lower()}" onclick="toggleBucketDetail(this)">'
                f'<td><span class="bucket-arrow">&#9658;</span> <strong>{bucket_name}</strong></td>'
                f"<td>{total}</td><td{crit_cls}>{critical}</td><td{high_cls}>{high}</td>"
                f'</tr><tr class="bucket-detail-row" style="display:none;">'
                f'<td colspan="4" class="vuln-table-note">'
                f"&#9888; Detail unavailable &mdash; findings are beyond the 50-result limit.</td></tr>"
            )
            continue

        # Truncation note when fetched < accurate total
        truncation_note = ""
        if fetched_count < total:
            truncation_note = (
                f'<p class="vuln-table-note">&#9888; Top {fetched_count:,} of {total:,} findings shown.</p>'
            )

        rows = []
        for idx, v in enumerate(vulns):
            sev = v.severity.lower()
            rows.append(
                f'<tr data-severity="{sev}" data-idx="{idx}">'
                f'<td><span class="badge badge-{sev}">{_escape_html(v.severity)}</span></td>'
                f'<td class="vuln-source">{_escape_html(v.source or "")}</td>'
                f"<td>{_escape_html(v.status)}</td>"
                f"<td>{v.age_days}</td>"
                f"<td>{_escape_html(v.title or '')}</td>"
                f'<td class="vuln-id">{_escape_html(v.id)}</td></tr>'
            )

        search_bar = (
            f'<div class="bucket-filter-bar">'
            f'<input type="text" class="bucket-search-input" placeholder="Search vulnerabilities..."'
            f' oninput="filterBucketVulns(this)">'
            f'<div class="bucket-filter-buttons">'
            f'<button class="active" data-sev="all" onclick="filterBucketSeverity(this,\'all\')">'
            f"All ({fetched_count})</button>"
            f'<button data-sev="critical" onclick="filterBucketSeverity(this,\'critical\')">'
            f"Critical ({sum(1 for v in vulns if v.severity.upper() == 'CRITICAL')})</button>"
            f'<button data-sev="high" onclick="filterBucketSeverity(this,\'high\')">'
            f"High ({sum(1 for v in vulns if v.severity.upper() == 'HIGH')})</button>"
            f"</div></div>"
        )

        table_body += (
            f'<tr class="bucket-row expandable" data-bucket="{bucket_name.lower()}" onclick="toggleBucketDetail(this)">'
            f'<td><span class="bucket-arrow">&#9658;</span> <strong>{bucket_name}</strong></td>'
            f"<td>{total}</td>"
            f"<td{crit_cls}>{critical}</td>"
            f"<td{high_cls}>{high}</td>"
            f"</tr>"
            f'<tr class="bucket-detail-row" style="display:none;">'
            f'<td colspan="4">{truncation_note}{search_bar}'
            f'<table class="vuln-table">{thead}<tbody>{"".join(rows)}</tbody></table>'
            f"</td></tr>"
        )

    if not table_body:
        table_body = '<tr><td colspan="4" class="no-findings">No Critical or High findings</td></tr>'

    return (
        '<div class="detail-section">'
        '<table class="bucket-summary-table">'
        "<thead><tr><th>Finding Type</th><th>Total</th><th>Critical</th><th>High</th></tr></thead>"
        f"<tbody>{table_body}</tbody>"
        "</table></div>"
    )


def _build_context(
    metrics_by_product: dict,
    vulns_by_product: dict,
    summary_stats: dict,
    bucket_counts_by_product: dict,
    accurate_totals: dict,
    aql_by_product: dict | None = None,
    dashboard_mode: str = "code_cloud",
) -> dict:
    """Stage 3: Build template context.

    Args:
        dashboard_mode: "code_cloud" (default) or "infrastructure" — controls which
                        bucket totals, filter categories, and expanded rows are shown.
    """
    active_buckets = _CODE_CLOUD_BUCKETS if dashboard_mode == "code_cloud" else _INFRA_BUCKETS

    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#0f172a",
        header_gradient_end="#0f172a",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=False,
    )

    # Header totals: sum per-bucket AQL counts filtered to active mode buckets.
    # Using bucket_counts_by_product (not aql_by_product) so mode boundaries are respected.
    mode_critical, mode_high = 0, 0
    for product_buckets in bucket_counts_by_product.values():
        for bucket_name, counts in product_buckets.items():
            if bucket_name in active_buckets:
                mode_critical += counts.get("critical", 0)
                mode_high += counts.get("high", 0)

    summary_cards = [
        summary_card("Priority Findings", str(mode_critical + mode_high)),
        summary_card("Critical", str(mode_critical), css_class="critical"),
        summary_card("High", str(mode_high), css_class="high"),
        summary_card("Products", str(summary_stats["product_count"])),
    ]

    # Active source names for vuln filtering in expanded rows
    active_source_names: set[str] = set()
    for bucket in active_buckets:
        active_source_names.update(BUCKET_SOURCE_MAP.get(bucket, []))

    products = []
    for product_name, metrics in sorted(metrics_by_product.items()):
        all_vulns = vulns_by_product.get(product_name, [])
        product_bucket_counts = bucket_counts_by_product.get(product_name)

        # Filter bucket counts to mode-active buckets only
        filtered_bucket_counts = (
            {b: c for b, c in product_bucket_counts.items() if b in active_buckets} if product_bucket_counts else {}
        )

        # Display counts from mode-filtered buckets
        display_critical = sum(b["critical"] for b in filtered_bucket_counts.values())
        display_high = sum(b["high"] for b in filtered_bucket_counts.values())

        if display_critical >= 5:
            status = "Critical"
            status_class = "action"
            status_priority = 0
        elif display_critical > 0:
            status = "High Risk"
            status_class = "caution"
            status_priority = 1
        elif display_high >= 10:
            status = "Monitor"
            status_class = "caution"
            status_priority = 2
        else:
            status = "OK"
            status_class = "good"
            status_priority = 3

        # Filter vulns to active-bucket sources for expanded row accuracy
        mode_vulns = [v for v in all_vulns if (v.source or "") in active_source_names]
        expanded_html = _generate_bucket_expanded_content(
            mode_vulns,
            bucket_counts=filtered_bucket_counts if filtered_bucket_counts else None,
        )

        categories = []
        bucket_detail: dict[str, dict] = {}
        for bucket in ["CODE", "CLOUD", "INFRASTRUCTURE"]:
            bkt_data = (product_bucket_counts or {}).get(bucket, {})
            bucket_detail[bucket.lower()] = {
                "critical": bkt_data.get("critical", 0),
                "high": bkt_data.get("high", 0),
            }
            if bucket in active_buckets and bkt_data.get("total", 0) > 0:
                categories.append(bucket.lower())

        products.append(
            {
                "name": product_name,
                "total": display_critical + display_high,
                "critical": display_critical,
                "high": display_high,
                "medium": metrics.medium,
                "status": status,
                "status_class": status_class,
                "status_priority": status_priority,
                "expanded_html": expanded_html,
                "categories": categories,
                "bucket_detail": bucket_detail,
            }
        )

    products.sort(key=lambda p: (p["status_priority"], -p["critical"], p["name"]))

    # category_counts: only keys relevant to this dashboard's filter bar
    category_counts: dict[str, int] = {}
    if "CODE" in active_buckets:
        category_counts["code"] = sum(
            counts.get("CODE", {}).get("total", 0) for counts in bucket_counts_by_product.values()
        )
    if "CLOUD" in active_buckets:
        category_counts["cloud"] = sum(
            counts.get("CLOUD", {}).get("total", 0) for counts in bucket_counts_by_product.values()
        )
    if "INFRASTRUCTURE" in active_buckets:
        category_counts["infrastructure"] = sum(
            counts.get("INFRASTRUCTURE", {}).get("total", 0) for counts in bucket_counts_by_product.values()
        )

    return {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "summary_cards": summary_cards,
        "products": products,
        "show_glossary": False,
        "category_counts": category_counts,
    }


def _generate_main_dashboard_html(
    metrics_by_product: dict,
    vulns_by_product: dict,
    bucket_counts_by_product: dict,
    accurate_totals: dict,
    aql_by_product: dict | None = None,
) -> str:
    """Generate Code & Cloud dashboard HTML using 4-stage pipeline."""
    summary_stats = _calculate_summary(metrics_by_product)
    context = _build_context(
        metrics_by_product,
        vulns_by_product,
        summary_stats,
        bucket_counts_by_product,
        accurate_totals,
        aql_by_product,
        dashboard_mode="code_cloud",
    )
    return render_dashboard("dashboards/security_dashboard.html", context)


def _generate_infra_dashboard_html(
    metrics_by_product: dict,
    vulns_by_product: dict,
    bucket_counts_by_product: dict,
    accurate_totals: dict,
    aql_by_product: dict | None = None,
) -> str:
    """Generate Infrastructure-only dashboard HTML using 4-stage pipeline."""
    summary_stats = _calculate_summary(metrics_by_product)
    context = _build_context(
        metrics_by_product,
        vulns_by_product,
        summary_stats,
        bucket_counts_by_product,
        accurate_totals,
        aql_by_product,
        dashboard_mode="infrastructure",
    )
    return render_dashboard("dashboards/security_infrastructure_dashboard.html", context)
