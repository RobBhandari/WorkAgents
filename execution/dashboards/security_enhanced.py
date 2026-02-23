#!/usr/bin/env python3
"""
Enhanced Security Dashboard Generator

Complete security dashboard with:
- Main summary table with VIEW buttons for drill-down
- Individual product detail pages
- Aging heatmap per product
- Live ArmorCode API queries
- Search, filter, and Excel export

This replaces the archived generate_security_dashboard_original.py with a
clean, maintainable implementation using modern architecture.

Usage:
    from execution.dashboards.security_enhanced import generate_security_dashboard_enhanced
    from pathlib import Path

    output_dir = Path('.tmp/observatory/dashboards')
    generate_security_dashboard_enhanced(output_dir)
"""

import json
from pathlib import Path

from execution.collectors.armorcode_vulnerability_loader import ArmorCodeVulnerabilityLoader
from execution.core import get_logger
from execution.dashboards.security_content_builder import (
    _generate_bucket_expanded_content,  # noqa: F401 — re-exported for test backward compat
    _generate_infra_dashboard_html,
    _generate_main_dashboard_html,
)
from execution.dashboards.security_helpers import (
    BUCKET_SOURCE_MAP,
    _calculate_summary,  # noqa: F401 — re-exported for test backward compat
    _group_findings_by_product,  # noqa: F401 — re-exported for test backward compat
    _metrics_from_aql_counts,
    _patch_history_bucket_breakdown,
    _update_history_current_total,
)
from execution.domain.security import BUCKET_ORDER, SOURCE_BUCKET_MAP, SecurityMetrics
from execution.secure_config import get_config

logger = get_logger(__name__)

ID_MAP_PATH = Path("data/armorcode_id_map.json")


def _load_id_map() -> dict[str, str]:
    """
    Load product name → ID mapping from data/armorcode_id_map.json.

    In CI/CD this file is written from the ARMORCODE_ID_MAP GitHub secret.
    Locally, run: python scripts/fetch_armorcode_id_map.py

    Returns:
        Dict mapping product_name -> product_id

    Raises:
        FileNotFoundError: If id map file doesn't exist
    """
    if not ID_MAP_PATH.exists():
        raise FileNotFoundError(
            f"{ID_MAP_PATH} not found. "
            "In CI/CD this is written from the ARMORCODE_ID_MAP secret. "
            "Locally, run: python scripts/fetch_armorcode_id_map.py"
        )
    name_to_id: dict[str, str] = json.loads(ID_MAP_PATH.read_text(encoding="utf-8"))
    logger.info(f"Loaded {len(name_to_id)} products from {ID_MAP_PATH}")
    return name_to_id


def generate_security_dashboard_enhanced(output_dir: Path | None = None) -> tuple[str, int]:
    """
    Generate enhanced security dashboard with expandable rows.

    Args:
        output_dir: Directory to write HTML files (defaults to .tmp/observatory/dashboards)

    Returns:
        Tuple of (main_dashboard_html, 0) - detail pages no longer generated

    Example:
        html, _ = generate_security_dashboard_enhanced()
        logger.info("Dashboard generated with expandable rows")
    """
    if output_dir is None:
        output_dir = Path(".tmp/observatory/dashboards")

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Enhanced Security Dashboard Generator")

    # Stage 1a: Load product name → ID mapping (from ARMORCODE_ID_MAP secret file).
    logger.info("Loading product ID map")
    try:
        product_id_map = _load_id_map()  # {name: id}
    except FileNotFoundError as e:
        logger.warning(
            "ArmorCode ID map not found, returning empty result",
            extra={
                "error_type": "ID map loading",
                "exception_class": e.__class__.__name__,
                "context": {"output_dir": str(output_dir)},
                "default_value": "('', 0)",
            },
        )
        return "", 0

    known_products = list(product_id_map.keys())
    id_to_name: dict[str, str] = {v: k for k, v in product_id_map.items()}

    hierarchy = get_config().get_optional_env("ARMORCODE_HIERARCHY")
    if not hierarchy:
        logger.warning("ARMORCODE_HIERARCHY not set — cannot load Production-only security data")
        return "", 0

    vuln_loader = ArmorCodeVulnerabilityLoader()

    # Stage 1c: Accurate per-product Critical + High counts via AQL count endpoint (2 calls).
    logger.info("Fetching per-product Critical/High counts via AQL (Production only)")
    crit_by_pid = vuln_loader.count_by_severity_aql("Critical", hierarchy, environment="Production")
    high_by_pid = vuln_loader.count_by_severity_aql("High", hierarchy, environment="Production")

    aql_by_product: dict[str, dict] = {}
    for pid, c in crit_by_pid.items():
        name = id_to_name.get(pid, pid)
        aql_by_product.setdefault(name, {"critical": 0, "high": 0})["critical"] = c
    for pid, h in high_by_pid.items():
        name = id_to_name.get(pid, pid)
        aql_by_product.setdefault(name, {"critical": 0, "high": 0})["high"] = h

    metrics_by_product = _metrics_from_aql_counts(aql_by_product)

    # Zero-pad: ensure all known products appear even with 0 Critical/High in Production.
    # known_products comes from ARMORCODE_ID_MAP secret (CI) or data/armorcode_id_map.json (local).
    from datetime import datetime as _dt

    for product_name in known_products:
        if product_name not in metrics_by_product:
            metrics_by_product[product_name] = SecurityMetrics(
                timestamp=_dt.now(),
                project=product_name,
                total_vulnerabilities=0,
                critical=0,
                high=0,
                medium=0,
                low=0,
            )
    logger.info("Security data loaded", extra={"product_count": len(metrics_by_product)})

    # Stage 1d: Per-bucket Critical/High counts via AQL (6 calls: 2 sev × 3 buckets).
    logger.info("Fetching per-bucket Critical/High counts via AQL (Production only)")
    _infra_cloud_providers = ["aws", "azure"]
    bucket_counts_by_product: dict[str, dict] = {}
    for bucket_name, bucket_sources in BUCKET_SOURCE_MAP.items():
        if bucket_name == "Other":
            continue
        cloud_providers = _infra_cloud_providers if bucket_name == "INFRASTRUCTURE" else None
        b_crit = vuln_loader.count_by_severity_aql(
            "Critical",
            hierarchy,
            environment="Production",
            sources=bucket_sources,
            asset_cloud_providers=cloud_providers,
        )
        b_high = vuln_loader.count_by_severity_aql(
            "High",
            hierarchy,
            environment="Production",
            sources=bucket_sources,
            asset_cloud_providers=cloud_providers,
        )
        for pid in set(b_crit) | set(b_high):
            name = id_to_name.get(pid, pid)
            c = b_crit.get(pid, 0)
            h = b_high.get(pid, 0)
            bucket_counts_by_product.setdefault(name, {})[bucket_name] = {
                "total": c + h,
                "critical": c,
                "high": h,
            }

    # Stage 1e: Display records per product per bucket (up to 50/combination).
    logger.info("Fetching display records per product per bucket (up to 50 each, Production only)")
    vulns_by_product: dict[str, list] = {}
    for product_name, pid in product_id_map.items():
        for bucket_name, bucket_sources in BUCKET_SOURCE_MAP.items():
            if bucket_name == "Other":
                continue
            bucket_total = bucket_counts_by_product.get(product_name, {}).get(bucket_name, {}).get("total", 0)
            if bucket_total == 0:
                continue
            records = vuln_loader.fetch_findings_aql(
                hierarchy,
                environment="Production",
                sources=bucket_sources,
                page_size=50,
                product_id=pid,
            )
            for record in records:
                vulns_by_product.setdefault(product_name, []).append(record)

    acc_c = sum(d.get("critical", 0) for d in aql_by_product.values())
    acc_h = sum(d.get("high", 0) for d in aql_by_product.values())

    main_html = _generate_main_dashboard_html(
        metrics_by_product, vulns_by_product, bucket_counts_by_product, {}, aql_by_product
    )

    _update_history_current_total(Path(".tmp/observatory/security_history.json"), acc_c, acc_h)
    _patch_history_bucket_breakdown(
        Path(".tmp/observatory/security_history.json"),
        bucket_counts_by_product,
    )

    main_file = output_dir / "security_dashboard.html"
    main_file.write_text(main_html, encoding="utf-8")
    logger.info("Security dashboard written", extra={"path": str(main_file)})

    infra_html = _generate_infra_dashboard_html(
        metrics_by_product, vulns_by_product, bucket_counts_by_product, {}, aql_by_product
    )
    infra_file = output_dir / "security_infrastructure_dashboard.html"
    infra_file.write_text(infra_html, encoding="utf-8")
    logger.info("Security infrastructure dashboard written", extra={"path": str(infra_file)})

    return main_html, 0


def main() -> None:
    """Command-line entry point"""
    output_dir = Path(".tmp/observatory/dashboards")
    generate_security_dashboard_enhanced(output_dir)


if __name__ == "__main__":
    main()
