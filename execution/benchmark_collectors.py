#!/usr/bin/env python3
"""
Benchmark Synchronous vs Async Collectors

Measures actual speedup achieved by async optimization.

Runs:
1. Synchronous collectors (baseline)
2. Async collectors (optimized)
3. Calculates speedup ratio
4. Saves results to JSON

Expected: 3-5x speedup
"""

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from execution.core import get_logger, setup_logging

setup_logging(level="INFO", json_output=False)
logger = get_logger(__name__)


class CollectorBenchmark:
    """Benchmark collector performance"""

    def benchmark_sync_subset(self) -> float:
        """
        Benchmark key synchronous collectors (ArmorCode, ADO Quality, ADO Flow).

        Returns:
            Total duration in seconds
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info("BENCHMARK: Synchronous Collectors")
        logger.info("=" * 60)

        collectors = [
            ("execution/armorcode_enhanced_metrics.py", "Security Metrics (ArmorCode)"),
            ("execution/ado_quality_metrics.py", "Quality Metrics"),
            ("execution/ado_flow_metrics.py", "Flow Metrics"),
        ]

        start = time.time()

        for script, name in collectors:
            logger.info(f"Running {name}...")
            result = subprocess.run([sys.executable, script], capture_output=True, text=True, check=False)

            if result.returncode == 0:
                logger.info(f"  [✓] {name} - SUCCESS")
            else:
                logger.error(f"  [✗] {name} - FAILED (exit code: {result.returncode})")

        duration = time.time() - start
        logger.info("")
        logger.info(f"Synchronous total: {duration:.2f}s ({duration / 60:.1f} minutes)")
        logger.info("=" * 60)

        return duration

    async def benchmark_async_subset(self) -> float:
        """
        Benchmark async collectors (ArmorCode, ADO Quality, ADO Flow).

        Returns:
            Total duration in seconds
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info("BENCHMARK: Async Collectors (Concurrent)")
        logger.info("=" * 60)

        from execution.collectors.async_ado_collector import AsyncADOCollector
        from execution.collectors.async_armorcode_collector import AsyncArmorCodeCollector

        start = time.time()

        # ArmorCode async
        async def collect_armorcode():
            from execution.armorcode_enhanced_metrics import load_existing_baseline, save_security_metrics

            baseline = load_existing_baseline()
            if not baseline:
                logger.error("ArmorCode baseline not found")
                return False

            collector = AsyncArmorCodeCollector()
            metrics = await collector.collect_metrics(baseline)

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "metrics": metrics,
                "config": {"lookback_days": 90, "async": True},
            }

            save_security_metrics(week_metrics)
            return True

        # ADO Quality async
        async def collect_ado_quality():
            from execution.collectors.ado_quality_metrics import get_ado_connection, save_quality_metrics

            with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
                projects = json.load(f)["projects"]

            connection = get_ado_connection()
            collector = AsyncADOCollector(max_workers=10)

            try:
                config = {"lookback_days": 90}
                project_metrics = await collector.collect_all_projects(
                    connection, projects, config, collector_type="quality"
                )

                week_metrics = {
                    "week_date": datetime.now().strftime("%Y-%m-%d"),
                    "week_number": datetime.now().isocalendar()[1],
                    "projects": project_metrics,
                    "config": {**config, "async": True},
                }

                save_quality_metrics(week_metrics)
                return True
            finally:
                collector.shutdown()

        # ADO Flow async
        async def collect_ado_flow():
            from execution.collectors.ado_flow_metrics import get_ado_connection, save_flow_metrics

            with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
                projects = json.load(f)["projects"]

            connection = get_ado_connection()
            collector = AsyncADOCollector(max_workers=10)

            try:
                config = {"lookback_days": 90, "aging_threshold_days": 30}
                project_metrics = await collector.collect_all_projects(
                    connection, projects, config, collector_type="flow"
                )

                week_metrics = {
                    "week_date": datetime.now().strftime("%Y-%m-%d"),
                    "week_number": datetime.now().isocalendar()[1],
                    "projects": project_metrics,
                    "config": {**config, "async": True},
                }

                save_flow_metrics(week_metrics)
                return True
            finally:
                collector.shutdown()

        # Run all concurrently
        logger.info("Running ArmorCode, ADO Quality, and ADO Flow concurrently...")
        results = await asyncio.gather(
            collect_armorcode(), collect_ado_quality(), collect_ado_flow(), return_exceptions=True
        )

        duration = time.time() - start

        # Check results
        success_count = sum(1 for r in results if r is True)
        error_count = sum(1 for r in results if isinstance(r, Exception))

        logger.info("")
        logger.info(f"Async total: {duration:.2f}s ({duration / 60:.1f} minutes)")
        logger.info(f"Success: {success_count}/3, Errors: {error_count}/3")
        logger.info("=" * 60)

        return duration

    async def run_comparison(self):
        """Run full comparison benchmark"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("COLLECTOR PERFORMANCE BENCHMARK")
        logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        logger.info("")

        # Benchmark sync
        logger.info("Phase 1: Measuring synchronous baseline...")
        sync_duration = self.benchmark_sync_subset()

        logger.info("")
        logger.info("Waiting 5 seconds before async benchmark...")
        await asyncio.sleep(5)

        # Benchmark async
        logger.info("Phase 2: Measuring async optimized...")
        async_duration = await self.benchmark_async_subset()

        # Calculate speedup
        speedup = sync_duration / async_duration if async_duration > 0 else 0
        time_saved = sync_duration - async_duration

        # Results
        logger.info("")
        logger.info("=" * 60)
        logger.info("BENCHMARK RESULTS")
        logger.info("=" * 60)
        logger.info(f"Synchronous:  {sync_duration:6.2f}s ({sync_duration / 60:5.1f} min)")
        logger.info(f"Async:        {async_duration:6.2f}s ({async_duration / 60:5.1f} min)")
        logger.info(f"Time Saved:   {time_saved:6.2f}s ({time_saved / 60:5.1f} min)")
        logger.info(f"Speedup:      {speedup:6.2f}x")
        logger.info("=" * 60)
        logger.info("")

        if speedup >= 3.0:
            logger.info("✓ Target achieved: 3-5x speedup!")
        elif speedup >= 2.0:
            logger.info("⚠ Partial improvement: 2-3x speedup")
        else:
            logger.info("✗ Target not met: <2x speedup")

        logger.info("")

        results = {
            "benchmark_date": datetime.now().isoformat(),
            "sync_duration_seconds": sync_duration,
            "async_duration_seconds": async_duration,
            "speedup": round(speedup, 2),
            "time_saved_seconds": time_saved,
            "time_saved_minutes": round(time_saved / 60, 1),
            "target_met": speedup >= 3.0,
        }

        return results


async def main():
    """Main entry point"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    benchmark = CollectorBenchmark()
    results = await benchmark.run_comparison()

    # Save benchmark results
    output_dir = Path(".tmp/observatory")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "benchmark_results.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Benchmark results saved to: {output_file}")
    logger.info("")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
