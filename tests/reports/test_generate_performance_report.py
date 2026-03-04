"""Tests for execution/generate_performance_report.py"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from execution.generate_performance_report import PerformanceReportGenerator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RESULTS: dict = {
    "sequential": {
        "platform": "Windows",
        "python_version": "3.11.0",
        "total_duration_seconds": 120.0,
        "total_duration_minutes": 2.0,
        "total_api_calls": 50,
        "average_throughput_per_sec": 0.42,
        "success_rate_percent": 100.0,
        "collectors": [
            {
                "name": "quality",
                "duration_seconds": 30.0,
                "api_calls_made": 10,
                "memory_peak_mb": 50.0,
                "throughput_per_sec": 0.33,
                "success": True,
            },
            {
                "name": "deployment",
                "duration_seconds": 60.0,
                "api_calls_made": 20,
                "memory_peak_mb": 80.0,
                "throughput_per_sec": 0.33,
                "success": True,
            },
        ],
    },
    "concurrent": {
        "platform": "Windows",
        "python_version": "3.11.0",
        "total_duration_seconds": 40.0,
        "total_duration_minutes": 0.67,
        "total_api_calls": 50,
        "average_throughput_per_sec": 1.25,
        "success_rate_percent": 100.0,
        "collectors": [
            {
                "name": "quality",
                "duration_seconds": 10.0,
                "api_calls_made": 10,
                "memory_peak_mb": 55.0,
                "throughput_per_sec": 1.0,
                "success": True,
            },
            {
                "name": "deployment",
                "duration_seconds": 15.0,
                "api_calls_made": 20,
                "memory_peak_mb": 85.0,
                "throughput_per_sec": 1.33,
                "success": True,
            },
        ],
    },
    "comparison": {
        "speedup_factor": 3.0,
        "actual_speedup": "3.00x",
        "target_range": "3-50x",
        "claim_validated": True,
        "time_saved_seconds": 80.0,
        "time_saved_minutes": 1.33,
    },
}


@pytest.fixture
def results_file(tmp_path: Path) -> Path:
    """Write sample results JSON to a temp file and return the path."""
    path = tmp_path / "benchmark_results.json"
    path.write_text(json.dumps(SAMPLE_RESULTS), encoding="utf-8")
    return path


@pytest.fixture
def generator(results_file: Path) -> PerformanceReportGenerator:
    """Return a PerformanceReportGenerator loaded with sample data."""
    return PerformanceReportGenerator(results_file)


# ---------------------------------------------------------------------------
# _load_results
# ---------------------------------------------------------------------------


def test_load_results_raises_for_missing_file(tmp_path: Path) -> None:
    """FileNotFoundError is raised when the input file does not exist."""
    with pytest.raises(FileNotFoundError, match="Benchmark results not found"):
        PerformanceReportGenerator(tmp_path / "no_such_file.json")


def test_load_results_populates_results(generator: PerformanceReportGenerator) -> None:
    """Results are loaded into the instance after construction."""
    assert "sequential" in generator.results
    assert "concurrent" in generator.results
    assert "comparison" in generator.results


# ---------------------------------------------------------------------------
# _build_collector_comparison_rows
# ---------------------------------------------------------------------------


def test_build_collector_comparison_rows_returns_rows(generator: PerformanceReportGenerator) -> None:
    seq = {c["name"]: c for c in SAMPLE_RESULTS["sequential"]["collectors"]}
    conc = {c["name"]: c for c in SAMPLE_RESULTS["concurrent"]["collectors"]}
    rows = generator._build_collector_comparison_rows(seq, conc)
    assert len(rows) == 2
    # Rows are sorted alphabetically: "deployment" < "quality"
    assert "deployment" in rows[0]
    assert "quality" in rows[1]


def test_build_collector_comparison_rows_empty_on_no_match(generator: PerformanceReportGenerator) -> None:
    rows = generator._build_collector_comparison_rows({}, {})
    assert rows == []


def test_build_collector_comparison_rows_skips_failed(generator: PerformanceReportGenerator) -> None:
    seq = {"quality": {"name": "quality", "duration_seconds": 30.0, "success": False}}
    conc = {"quality": {"name": "quality", "duration_seconds": 10.0, "success": True}}
    rows = generator._build_collector_comparison_rows(seq, conc)
    assert rows == []


# ---------------------------------------------------------------------------
# _build_detailed_metrics_rows
# ---------------------------------------------------------------------------


def test_build_detailed_metrics_rows_returns_rows(generator: PerformanceReportGenerator) -> None:
    rows = generator._build_detailed_metrics_rows(SAMPLE_RESULTS["concurrent"])
    assert len(rows) == 2
    assert "quality" in rows[0]
    assert "Success" in rows[0]


def test_build_detailed_metrics_rows_empty_collectors(generator: PerformanceReportGenerator) -> None:
    rows = generator._build_detailed_metrics_rows({})
    assert rows == []


def test_build_detailed_metrics_rows_failed_collector(generator: PerformanceReportGenerator) -> None:
    concurrent = {
        "collectors": [
            {
                "name": "risk",
                "duration_seconds": 5.0,
                "api_calls_made": 3,
                "memory_peak_mb": 20.0,
                "throughput_per_sec": 0.6,
                "success": False,
            }
        ]
    }
    rows = generator._build_detailed_metrics_rows(concurrent)
    assert len(rows) == 1
    assert "Failed" in rows[0]


# ---------------------------------------------------------------------------
# _build_collector_insights
# ---------------------------------------------------------------------------


def test_build_collector_insights_returns_two_bullets(generator: PerformanceReportGenerator) -> None:
    seq = {c["name"]: c for c in SAMPLE_RESULTS["sequential"]["collectors"]}
    conc = {c["name"]: c for c in SAMPLE_RESULTS["concurrent"]["collectors"]}
    lines = generator._build_collector_insights(seq, conc)
    assert len(lines) == 2
    assert "Fastest" in lines[0]
    assert "Slowest" in lines[1]


def test_build_collector_insights_empty_on_no_collectors(generator: PerformanceReportGenerator) -> None:
    lines = generator._build_collector_insights({}, {})
    assert lines == []


def test_build_collector_insights_fastest_has_highest_speedup(generator: PerformanceReportGenerator) -> None:
    """deployment speedup = 60/15 = 4x; quality speedup = 30/10 = 3x → deployment is fastest."""
    seq = {c["name"]: c for c in SAMPLE_RESULTS["sequential"]["collectors"]}
    conc = {c["name"]: c for c in SAMPLE_RESULTS["concurrent"]["collectors"]}
    lines = generator._build_collector_insights(seq, conc)
    assert "deployment" in lines[0]  # fastest
    assert "quality" in lines[1]  # slowest


# ---------------------------------------------------------------------------
# generate_markdown_report
# ---------------------------------------------------------------------------


def test_generate_markdown_report_is_non_empty_string(generator: PerformanceReportGenerator) -> None:
    md = generator.generate_markdown_report()
    assert isinstance(md, str)
    assert len(md) > 100


def test_generate_markdown_report_contains_key_sections(generator: PerformanceReportGenerator) -> None:
    md = generator.generate_markdown_report()
    assert "# REST API v7.1 Migration Performance Report" in md
    assert "## Executive Summary" in md
    assert "## Overall Performance Comparison" in md
    assert "## Collector-by-Collector Performance" in md
    assert "## Detailed Concurrent Collector Metrics" in md
    assert "## Key Findings" in md
    assert "## Conclusion" in md


def test_generate_markdown_report_empty_results(results_file: Path, tmp_path: Path) -> None:
    """An empty results dict should not raise — graceful zero values."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}", encoding="utf-8")
    gen = PerformanceReportGenerator(empty_file)
    md = gen.generate_markdown_report()
    assert isinstance(md, str)
    assert "REST API v7.1 Migration Performance Report" in md


# ---------------------------------------------------------------------------
# _build_html_head
# ---------------------------------------------------------------------------


def test_build_html_head_returns_non_empty_list(generator: PerformanceReportGenerator) -> None:
    head = generator._build_html_head()
    assert isinstance(head, list)
    assert len(head) > 0


def test_build_html_head_contains_doctype(generator: PerformanceReportGenerator) -> None:
    head = generator._build_html_head()
    combined = "".join(head)
    assert "<!DOCTYPE html>" in combined
    assert "<head>" in combined
    assert "<style>" in combined
    assert "</head>" in combined


# ---------------------------------------------------------------------------
# _convert_table_row_to_html
# ---------------------------------------------------------------------------


def test_convert_table_row_header(generator: PerformanceReportGenerator) -> None:
    line = "| Name | Value |"
    html = generator._convert_table_row_to_html(line, is_header=True)
    combined = "".join(html)
    assert "<th>Name</th>" in combined
    assert "<th>Value</th>" in combined
    assert "<tr>" in combined


def test_convert_table_row_data(generator: PerformanceReportGenerator) -> None:
    line = "| **foo** | bar |"
    html = generator._convert_table_row_to_html(line, is_header=False)
    combined = "".join(html)
    assert "<td>" in combined
    assert "<strong>" in combined


# ---------------------------------------------------------------------------
# _convert_line_to_html
# ---------------------------------------------------------------------------


def test_convert_line_h1(generator: PerformanceReportGenerator) -> None:
    assert generator._convert_line_to_html("# Hello") == "    <h1>Hello</h1>\n"


def test_convert_line_h2(generator: PerformanceReportGenerator) -> None:
    assert generator._convert_line_to_html("## Hello") == "    <h2>Hello</h2>\n"


def test_convert_line_h3(generator: PerformanceReportGenerator) -> None:
    assert generator._convert_line_to_html("### Hello") == "    <h3>Hello</h3>\n"


def test_convert_line_hr(generator: PerformanceReportGenerator) -> None:
    assert generator._convert_line_to_html("---") == "    <hr>\n"


def test_convert_line_italic(generator: PerformanceReportGenerator) -> None:
    result = generator._convert_line_to_html("*italic text*")
    assert "<em>" in result
    assert "italic text" in result


def test_convert_line_blank(generator: PerformanceReportGenerator) -> None:
    assert generator._convert_line_to_html("") == ""
    assert generator._convert_line_to_html("   ") == ""


def test_convert_line_paragraph_with_bold(generator: PerformanceReportGenerator) -> None:
    result = generator._convert_line_to_html("This is **bold** text.")
    assert "<p>" in result
    assert "<strong>" in result


# ---------------------------------------------------------------------------
# _handle_table_row
# ---------------------------------------------------------------------------


def test_handle_table_row_opens_table_on_first_call(generator: PerformanceReportGenerator) -> None:
    html_lines: list[str] = []
    in_table, table_headers = generator._handle_table_row("| A | B |", html_lines, False, False)
    assert in_table is True
    assert "    <table>\n" in html_lines


def test_handle_table_row_separator_sets_headers_false(generator: PerformanceReportGenerator) -> None:
    html_lines: list[str] = ["    <table>\n"]
    in_table, table_headers = generator._handle_table_row("| --- | --- |", html_lines, True, True)
    assert table_headers is False


def test_handle_table_row_does_not_reopen_table(generator: PerformanceReportGenerator) -> None:
    html_lines: list[str] = ["    <table>\n"]
    generator._handle_table_row("| X | Y |", html_lines, True, False)
    assert html_lines.count("    <table>\n") == 1


# ---------------------------------------------------------------------------
# _process_markdown_lines
# ---------------------------------------------------------------------------


def test_process_markdown_lines_handles_table(generator: PerformanceReportGenerator) -> None:
    lines = [
        "| Header |",
        "| --- |",
        "| Data |",
        "",
    ]
    result = "".join(generator._process_markdown_lines(lines))
    assert "<table>" in result
    assert "</table>" in result
    assert "<th>" in result
    assert "<td>" in result


def test_process_markdown_lines_closes_table_at_end(generator: PerformanceReportGenerator) -> None:
    """Table that ends at last line should still be closed."""
    lines = ["| A |", "| --- |", "| B |"]
    result = "".join(generator._process_markdown_lines(lines))
    assert "</table>" in result


def test_process_markdown_lines_empty_input(generator: PerformanceReportGenerator) -> None:
    result = generator._process_markdown_lines([])
    assert result == []


# ---------------------------------------------------------------------------
# generate_html_report
# ---------------------------------------------------------------------------


def test_generate_html_report_returns_non_empty_string(generator: PerformanceReportGenerator) -> None:
    md = generator.generate_markdown_report()
    html = generator.generate_html_report(md)
    assert isinstance(html, str)
    assert len(html) > 200


def test_generate_html_report_structure(generator: PerformanceReportGenerator) -> None:
    md = generator.generate_markdown_report()
    html = generator.generate_html_report(md)
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html
    assert "<head>" in html
    assert "<body>" in html
    assert "</html>" in html


def test_generate_html_report_contains_headings(generator: PerformanceReportGenerator) -> None:
    md = generator.generate_markdown_report()
    html = generator.generate_html_report(md)
    assert "<h1>" in html
    assert "<h2>" in html


def test_generate_html_report_contains_tables(generator: PerformanceReportGenerator) -> None:
    md = generator.generate_markdown_report()
    html = generator.generate_html_report(md)
    assert "<table>" in html
    assert "<th>" in html
    assert "<td>" in html


def test_generate_html_report_empty_markdown(generator: PerformanceReportGenerator) -> None:
    html = generator.generate_html_report("")
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


# ---------------------------------------------------------------------------
# save_reports (integration)
# ---------------------------------------------------------------------------


def test_save_reports_creates_files(generator: PerformanceReportGenerator, tmp_path: Path) -> None:
    generator.save_reports(tmp_path)
    assert (tmp_path / "performance_report.md").exists()
    assert (tmp_path / "performance_report.html").exists()


def test_save_reports_md_content(generator: PerformanceReportGenerator, tmp_path: Path) -> None:
    generator.save_reports(tmp_path)
    content = (tmp_path / "performance_report.md").read_text(encoding="utf-8")
    assert "REST API v7.1 Migration Performance Report" in content


def test_save_reports_html_content(generator: PerformanceReportGenerator, tmp_path: Path) -> None:
    generator.save_reports(tmp_path)
    content = (tmp_path / "performance_report.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
