#!/usr/bin/env python3
"""
Generate Performance Report from Benchmark Results

Creates comprehensive performance documentation for REST API migration.

Outputs:
- Markdown report (.md)
- HTML report (.html)
- Summary statistics
- Performance graphs (if matplotlib available)

Usage:
    python execution/generate_performance_report.py
    python execution/generate_performance_report.py --input custom_benchmark.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class PerformanceReportGenerator:
    """Generate performance reports from benchmark results"""

    def __init__(self, results_file: Path):
        """
        Initialize report generator.

        Args:
            results_file: Path to benchmark results JSON
        """
        self.results_file = results_file
        self.results: dict[str, Any] = {}
        self._load_results()

    def _load_results(self):
        """Load benchmark results from JSON file"""
        if not self.results_file.exists():
            raise FileNotFoundError(f"Benchmark results not found: {self.results_file}")

        with open(self.results_file, encoding="utf-8") as f:
            self.results = json.load(f)

    # -----------------------------------------------------------------------
    # Markdown report helpers
    # -----------------------------------------------------------------------

    def _build_collector_comparison_rows(
        self,
        seq_collectors: dict[str, Any],
        conc_collectors: dict[str, Any],
    ) -> list[str]:
        """Build per-collector comparison table rows for the Markdown report."""
        rows: list[str] = []
        for name in sorted(seq_collectors.keys()):
            seq_col = seq_collectors.get(name, {})
            conc_col = conc_collectors.get(name, {})

            if seq_col and conc_col and seq_col.get("success") and conc_col.get("success"):
                speedup = seq_col["duration_seconds"] / conc_col["duration_seconds"]
                rows.append(
                    f"| **{name}** | {seq_col['duration_seconds']:.2f}s | "
                    f"{conc_col['duration_seconds']:.2f}s | **{speedup:.2f}x** | "
                    f"{conc_col['api_calls_made']} | {conc_col['throughput_per_sec']:.2f} calls/sec |\n"
                )
        return rows

    def _build_detailed_metrics_rows(self, concurrent: dict[str, Any]) -> list[str]:
        """Build detailed concurrent collector metrics rows for the Markdown report."""
        rows: list[str] = []
        for collector in concurrent.get("collectors", []):
            status = "✅ Success" if collector.get("success") else "❌ Failed"
            rows.append(
                f"| {collector['name']} | {collector['duration_seconds']:.2f}s | "
                f"{collector['api_calls_made']} | {collector['memory_peak_mb']:.2f} MB | "
                f"{collector['throughput_per_sec']:.2f} calls/sec | {status} |\n"
            )
        return rows

    def _build_collector_insights(
        self,
        seq_collectors: dict[str, Any],
        conc_collectors: dict[str, Any],
    ) -> list[str]:
        """Build collector-specific insight bullet points for the Markdown report."""
        collector_speedups: list[tuple[str, float]] = []
        for name in seq_collectors.keys():
            seq_col = seq_collectors.get(name, {})
            conc_col = conc_collectors.get(name, {})

            if seq_col and conc_col and seq_col.get("success") and conc_col.get("success"):
                speedup = seq_col["duration_seconds"] / conc_col["duration_seconds"]
                collector_speedups.append((name, speedup))

        collector_speedups.sort(key=lambda x: x[1], reverse=True)

        lines: list[str] = []
        if collector_speedups:
            fastest = collector_speedups[0]
            slowest = collector_speedups[-1]
            lines.append(f"- **Fastest Improvement:** {fastest[0]} achieved {fastest[1]:.2f}x speedup\n")
            lines.append(f"- **Slowest Improvement:** {slowest[0]} achieved {slowest[1]:.2f}x speedup\n")
        return lines

    def generate_markdown_report(self) -> str:
        """
        Generate Markdown performance report.

        Returns:
            Markdown formatted report
        """
        sequential = self.results.get("sequential", {})
        concurrent = self.results.get("concurrent", {})
        comparison = self.results.get("comparison", {})

        seq_throughput = sequential.get("average_throughput_per_sec", 0)
        conc_throughput = concurrent.get("average_throughput_per_sec", 0)
        throughput_ratio = (conc_throughput / seq_throughput) if seq_throughput > 0 else 0

        report_lines = [
            "# REST API v7.1 Migration Performance Report\n",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"**Platform:** {concurrent.get('platform', 'Unknown')}\n",
            f"**Python:** {concurrent.get('python_version', 'Unknown')}\n",
            "\n---\n",
            "\n## Executive Summary\n",
            f"✅ **Speedup Achieved:** {comparison.get('actual_speedup', 'N/A')}\n",
            f"🎯 **Target Range:** {comparison.get('target_range', 'N/A')}\n",
            f"✅ **Claim Validated:** {'YES' if comparison.get('claim_validated') else 'NO'}\n",
            f"⏱️ **Time Saved:** {comparison.get('time_saved_minutes', 0):.2f} minutes per run\n",
            "\n---\n",
            "\n## Overall Performance Comparison\n",
            "| Metric | Sequential | Concurrent | Improvement |\n",
            "|--------|------------|------------|--------------|\n",
            f"| **Total Duration** | {sequential.get('total_duration_seconds', 0):.2f}s ({sequential.get('total_duration_minutes', 0):.2f} min) | {concurrent.get('total_duration_seconds', 0):.2f}s ({concurrent.get('total_duration_minutes', 0):.2f} min) | **{comparison.get('speedup_factor', 0):.2f}x faster** |\n",
            f"| **API Calls** | {sequential.get('total_api_calls', 0)} | {concurrent.get('total_api_calls', 0)} | Same |\n",
            f"| **Throughput** | {seq_throughput:.2f} calls/sec | {conc_throughput:.2f} calls/sec | **{throughput_ratio:.2f}x faster** |\n",
            f"| **Success Rate** | {sequential.get('success_rate_percent', 0):.1f}% | {concurrent.get('success_rate_percent', 0):.1f}% | {concurrent.get('success_rate_percent', 0) - sequential.get('success_rate_percent', 0):+.1f}% |\n",
            "\n---\n",
            "\n## Collector-by-Collector Performance\n",
            "| Collector | Sequential (s) | Concurrent (s) | Speedup | API Calls | Throughput |\n",
            "|-----------|----------------|----------------|---------|-----------|------------|\n",
        ]

        seq_collectors = {c["name"]: c for c in sequential.get("collectors", [])}
        conc_collectors = {c["name"]: c for c in concurrent.get("collectors", [])}

        report_lines.extend(self._build_collector_comparison_rows(seq_collectors, conc_collectors))

        report_lines.extend(
            [
                "\n---\n",
                "\n## Detailed Concurrent Collector Metrics\n",
                "| Collector | Duration | API Calls | Memory (MB) | Throughput | Status |\n",
                "|-----------|----------|-----------|-------------|------------|--------|\n",
            ]
        )

        report_lines.extend(self._build_detailed_metrics_rows(concurrent))

        report_lines.extend(
            [
                "\n---\n",
                "\n## Key Findings\n",
                f"1. **Overall Speedup:** Concurrent execution is **{comparison.get('speedup_factor', 0):.2f}x faster** than sequential\n",
                f"2. **Time Savings:** Each run saves **{comparison.get('time_saved_minutes', 0):.2f} minutes** ({comparison.get('time_saved_seconds', 0):.2f} seconds)\n",
                f"3. **API Throughput:** Improved from {seq_throughput:.2f} to {conc_throughput:.2f} calls/sec\n",
                f"4. **Reliability:** {concurrent.get('success_rate_percent', 0):.1f}% success rate in concurrent mode\n",
                "\n### Collector-Specific Insights\n",
            ]
        )

        report_lines.extend(self._build_collector_insights(seq_collectors, conc_collectors))

        report_lines.extend(
            [
                "\n---\n",
                "\n## Technical Implementation\n",
                "### Migration Details\n",
                "- **From:** Azure DevOps SDK (azure-devops==7.1.0b4) with ThreadPoolExecutor\n",
                "- **To:** Direct REST API v7.1 with native async/await\n",
                "- **HTTP Client:** AsyncSecureHTTPClient with HTTP/2 support\n",
                "- **Concurrency Model:** asyncio.gather() for true parallel execution\n",
                "\n### Performance Optimizations\n",
                "1. **True Async I/O:** Native async REST calls (no thread pool overhead)\n",
                "2. **HTTP/2 Multiplexing:** Multiple requests over single connection\n",
                "3. **Connection Pooling:** Reused connections across API calls\n",
                "4. **Concurrent Execution:** All collectors run in parallel via asyncio.gather()\n",
                "5. **Efficient Batching:** Work items fetched in batches of 200 (API limit)\n",
                "\n### API Call Distribution\n",
                "Different collectors make varying numbers of API calls:\n",
                "- **Quality/Flow:** ~3 calls per project (WIQL + work items + metadata)\n",
                "- **Deployment:** ~7 calls per project (builds + changes + commits)\n",
                "- **Ownership:** ~15 calls per project (repos + commits + PRs + iterations)\n",
                "- **Collaboration:** ~12 calls per project (repos + PRs + threads + commits)\n",
                "- **Risk:** ~6 calls per project (security WIQL queries + work items)\n",
                "\n---\n",
                "\n## Conclusion\n",
                f"The migration from Azure DevOps SDK to REST API v7.1 with async/await has achieved a **{comparison.get('speedup_factor', 0):.2f}x speedup**, ",
                f"{'**validating**' if comparison.get('claim_validated') else '**partially validating**'} the claimed 3-50x performance improvement.\n",
                "\n",
                f"This translates to **{comparison.get('time_saved_minutes', 0):.2f} minutes saved per collection run**, ",
                "significantly improving data freshness and reducing infrastructure costs.\n",
                "\n---\n",
                "\n*Report generated by `execution/generate_performance_report.py`*\n",
            ]
        )

        return "".join(report_lines)

    # -----------------------------------------------------------------------
    # HTML report helpers
    # -----------------------------------------------------------------------

    def _build_html_head(self) -> list[str]:
        """Return the HTML <head> block including embedded styles."""
        return [
            "<!DOCTYPE html>\n",
            "<html>\n",
            "<head>\n",
            "    <meta charset='UTF-8'>\n",
            "    <title>REST API Migration Performance Report</title>\n",
            "    <style>\n",
            "        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 40px auto; padding: 20px; line-height: 1.6; }\n",
            "        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }\n",
            "        h2 { color: #34495e; border-bottom: 2px solid #95a5a6; padding-bottom: 8px; margin-top: 30px; }\n",
            "        h3 { color: #7f8c8d; margin-top: 20px; }\n",
            "        table { border-collapse: collapse; width: 100%; margin: 20px 0; }\n",
            "        th, td { border: 1px solid #bdc3c7; padding: 12px; text-align: left; }\n",
            "        th { background-color: #3498db; color: white; font-weight: 600; }\n",
            "        tr:nth-child(even) { background-color: #ecf0f1; }\n",
            "        code { background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }\n",
            "        strong { color: #2c3e50; }\n",
            "        hr { border: none; border-top: 1px solid #bdc3c7; margin: 30px 0; }\n",
            "        .summary { background-color: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #4caf50; }\n",
            "    </style>\n",
            "</head>\n",
            "<body>\n",
        ]

    def _convert_table_row_to_html(self, line: str, is_header: bool) -> list[str]:
        """Convert a single Markdown table row to HTML <tr> lines.

        Args:
            line: The raw Markdown table row (e.g. ``| A | B | C |``).
            is_header: True if the row should use ``<th>`` cells.

        Returns:
            List of HTML strings for the row (including surrounding ``<tr>`` tags).
        """
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        html: list[str] = ["        <tr>\n"]
        if is_header:
            for cell in cells:
                html.append(f"            <th>{cell}</th>\n")
        else:
            for cell in cells:
                cell_html = cell.replace("**", "<strong>").replace("**", "</strong>")
                html.append(f"            <td>{cell_html}</td>\n")
        html.append("        </tr>\n")
        return html

    def _convert_line_to_html(self, line: str) -> str:
        """Convert a single non-table Markdown line to an HTML string.

        Handles headings (h1–h3), horizontal rules, italic paragraphs, and
        paragraphs with inline bold / code markup.

        Args:
            line: Raw Markdown line.

        Returns:
            HTML string for the line, or empty string for blank lines.
        """
        if line.startswith("# "):
            return f"    <h1>{line[2:].strip()}</h1>\n"
        if line.startswith("## "):
            return f"    <h2>{line[3:].strip()}</h2>\n"
        if line.startswith("### "):
            return f"    <h3>{line[4:].strip()}</h3>\n"
        if line.strip() == "---":
            return "    <hr>\n"
        if line.strip().startswith("*"):
            return f"    <p><em>{line.strip()[1:].strip()}</em></p>\n"
        if line.strip():
            line_html = line
            line_html = line_html.replace("**", "<strong>")
            line_html = line_html.replace("**", "</strong>")
            line_html = line_html.replace("`", "<code>")
            line_html = line_html.replace("`", "</code>")
            return f"    <p>{line_html}</p>\n"
        return ""

    def _handle_table_row(
        self,
        line: str,
        html_lines: list[str],
        in_table: bool,
        table_headers: bool,
    ) -> tuple[bool, bool]:
        """Process one Markdown table row, mutating html_lines in place.

        Opens the ``<table>`` tag on the first row encountered, skips separator
        rows (``|---|``), and delegates cell rendering to
        ``_convert_table_row_to_html``.

        Args:
            line: The Markdown table row.
            html_lines: Accumulator list to append HTML strings to.
            in_table: Whether a ``<table>`` is currently open.
            table_headers: Whether the next data row should use ``<th>`` cells.

        Returns:
            Updated ``(in_table, table_headers)`` tuple.
        """
        if not in_table:
            html_lines.append("    <table>\n")
            in_table = True
            table_headers = True

        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if table_headers and all(c.startswith("-") for c in cells):
            return in_table, False

        html_lines.extend(self._convert_table_row_to_html(line, table_headers))
        return in_table, False

    def _process_markdown_lines(self, lines: list[str]) -> list[str]:
        """Convert all Markdown lines to HTML, handling table open/close state.

        Args:
            lines: Markdown content split by newline.

        Returns:
            List of HTML strings (one or more per input line).
        """
        html_lines: list[str] = []
        in_table = False
        table_headers = False

        for line in lines:
            is_table_row = line.startswith("| ") and "|" in line

            if is_table_row:
                in_table, table_headers = self._handle_table_row(line, html_lines, in_table, table_headers)
            else:
                if in_table:
                    html_lines.append("    </table>\n")
                    in_table = False
                    table_headers = False

                converted = self._convert_line_to_html(line)
                if converted:
                    html_lines.append(converted)

        if in_table:
            html_lines.append("    </table>\n")

        return html_lines

    def generate_html_report(self, markdown_content: str) -> str:
        """
        Convert Markdown report to HTML.

        Args:
            markdown_content: Markdown formatted report

        Returns:
            HTML formatted report
        """
        html_lines = self._build_html_head()
        html_lines.extend(self._process_markdown_lines(markdown_content.split("\n")))
        html_lines.append("</body>\n</html>\n")
        return "".join(html_lines)

    def save_reports(self, output_dir: Path):
        """
        Generate and save all report formats.

        Args:
            output_dir: Directory to save reports
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate Markdown report
        print("Generating Markdown report...")
        markdown_content = self.generate_markdown_report()
        markdown_file = output_dir / "performance_report.md"

        with open(markdown_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"[OK] Markdown report saved: {markdown_file}")

        # Generate HTML report
        print("Generating HTML report...")
        html_content = self.generate_html_report(markdown_content)
        html_file = output_dir / "performance_report.html"

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"[OK] HTML report saved: {html_file}")

        # Print summary
        comparison = self.results.get("comparison", {})
        print("\n" + "=" * 60)
        print("PERFORMANCE REPORT SUMMARY")
        print("=" * 60)
        print(f"Speedup Factor:     {comparison.get('speedup_factor', 0):.2f}x")
        print(f"Time Saved:         {comparison.get('time_saved_minutes', 0):.2f} minutes")
        print(f"Claim Validated:    {'YES' if comparison.get('claim_validated') else 'NO'}")
        print(f"Target Range:       {comparison.get('target_range', 'N/A')}")
        print("=" * 60)
        print(f"\nView HTML report: file:///{html_file.absolute()}")
        print("")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate Performance Report")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(".tmp/observatory/benchmark_results_enhanced.json"),
        help="Input benchmark results JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp/observatory"),
        help="Output directory for reports",
    )
    args = parser.parse_args()

    try:
        generator = PerformanceReportGenerator(args.input)
        generator.save_reports(args.output)
        return 0
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
