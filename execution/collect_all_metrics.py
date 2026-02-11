#!/usr/bin/env python3
"""
Async Metrics Collection Orchestrator

Runs all collectors concurrently for maximum performance.

Performance:
- Sequential: 7 collectors × 30-60s = 3-7 minutes
- Concurrent: max(30-60s) = 30-60 seconds
- Speedup: 3-7x
"""

import asyncio
import sys
from datetime import datetime

from execution.core import get_logger

logger = get_logger(__name__)


class AsyncMetricsOrchestrator:
    """Orchestrates concurrent metrics collection"""

    async def _run_collector_async(self, collector_name: str, collector_func) -> tuple[str, bool, float]:
        """
        Run async collector and track duration.

        Args:
            collector_name: Display name for the collector
            collector_func: Async function to execute

        Returns:
            (collector_name, success, duration_seconds)
        """
        logger.info(f"[START] {collector_name}")
        start = datetime.now()

        try:
            await collector_func()
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"[SUCCESS] {collector_name} completed in {duration:.2f}s")
            return (collector_name, True, duration)

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"[FAILED] {collector_name} failed after {duration:.2f}s: {e}", exc_info=True)
            return (collector_name, False, duration)

    async def _run_sync_collector_subprocess(self, collector_name: str, script_path: str) -> tuple[str, bool, float]:
        """
        Run synchronous collector via subprocess (non-blocking).

        Used for collectors not yet converted to async.

        Args:
            collector_name: Display name
            script_path: Path to Python script

        Returns:
            (collector_name, success, duration_seconds)
        """
        logger.info(f"[START] {collector_name} (subprocess)")
        start = datetime.now()

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            duration = (datetime.now() - start).total_seconds()

            if process.returncode == 0:
                logger.info(f"[SUCCESS] {collector_name} completed in {duration:.2f}s")
                return (collector_name, True, duration)
            else:
                logger.error(
                    f"[FAILED] {collector_name} failed after {duration:.2f}s (exit code: {process.returncode})"
                )
                if stderr:
                    logger.error(f"stderr: {stderr.decode('utf-8', errors='replace')}")
                return (collector_name, False, duration)

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"[FAILED] {collector_name} error after {duration:.2f}s: {e}")
            return (collector_name, False, duration)

    async def collect_all_metrics(self) -> dict:
        """
        Collect all metrics concurrently.

        Strategy:
        1. Run async collectors directly (ArmorCode, ADO Quality, ADO Flow)
        2. Run sync collectors via subprocess (non-blocking)
        3. Wait for all to complete
        4. Return summary

        Returns:
            Summary dictionary with results and timings
        """
        logger.info("=" * 60)
        logger.info("Starting concurrent metrics collection")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Async collectors (direct execution)
        async_tasks = []

        # ArmorCode (async)
        async def collect_armorcode():
            import json

            from execution.armorcode_enhanced_metrics import load_existing_baseline, save_security_metrics
            from execution.collectors.async_armorcode_collector import AsyncArmorCodeCollector

            baseline = load_existing_baseline()
            if not baseline:
                logger.error("ArmorCode baseline not found - skipping")
                return

            collector = AsyncArmorCodeCollector()
            metrics = await collector.collect_metrics(baseline)

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "metrics": metrics,
                "config": {"lookback_days": 90, "async": True},
            }

            save_security_metrics(week_metrics)

        async_tasks.append(self._run_collector_async("Security Metrics (ArmorCode)", collect_armorcode))

        # ADO Quality (async via REST API)
        async def collect_ado_quality():
            import json

            from execution.collectors.ado_quality_metrics import save_quality_metrics
            from execution.collectors.ado_rest_client import get_ado_rest_client
            from execution.collectors.async_ado_collector import AsyncADOCollector

            with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
                projects = json.load(f)["projects"]

            rest_client = get_ado_rest_client()
            collector = AsyncADOCollector(rest_client)

            config = {"lookback_days": 90}
            project_metrics = await collector.collect_all_projects(projects, config, collector_type="quality")

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "projects": project_metrics,
                "config": {**config, "async": True},
            }

            save_quality_metrics(week_metrics)

        async_tasks.append(self._run_collector_async("Quality Metrics", collect_ado_quality))

        # ADO Flow (async via REST API)
        async def collect_ado_flow():
            import json

            from execution.collectors.ado_flow_metrics import save_flow_metrics
            from execution.collectors.ado_rest_client import get_ado_rest_client
            from execution.collectors.async_ado_collector import AsyncADOCollector

            with open(".tmp/observatory/ado_structure.json", encoding="utf-8") as f:
                projects = json.load(f)["projects"]

            rest_client = get_ado_rest_client()
            collector = AsyncADOCollector(rest_client)

            config = {"lookback_days": 90, "aging_threshold_days": 30}
            project_metrics = await collector.collect_all_projects(projects, config, collector_type="flow")

            week_metrics = {
                "week_date": datetime.now().strftime("%Y-%m-%d"),
                "week_number": datetime.now().isocalendar()[1],
                "projects": project_metrics,
                "config": {**config, "async": True},
            }

            save_flow_metrics(week_metrics)

        async_tasks.append(self._run_collector_async("Flow Metrics", collect_ado_flow))

        # Sync collectors (subprocess - these run concurrently too)
        sync_collectors = [
            ("Ownership Metrics", "execution/collectors/ado_ownership_metrics.py"),
            ("Risk Metrics", "execution/collectors/ado_risk_metrics.py"),
            ("Deployment Metrics (DORA)", "execution/collectors/ado_deployment_metrics.py"),
            ("Collaboration Metrics (PR Analysis)", "execution/collectors/ado_collaboration_metrics.py"),
        ]

        subprocess_tasks = [self._run_sync_collector_subprocess(name, path) for name, path in sync_collectors]

        # Run all collectors concurrently
        all_tasks = async_tasks + subprocess_tasks
        results = await asyncio.gather(*all_tasks)

        # Calculate summary
        total_duration = (datetime.now() - start_time).total_seconds()
        successful = sum(1 for _, success, _ in results if success)
        failed = len(results) - successful

        logger.info("")
        logger.info("=" * 60)
        logger.info("Collection Summary")
        logger.info("=" * 60)
        logger.info(f"Total duration: {total_duration:.2f}s ({total_duration / 60:.1f} minutes)")
        logger.info(f"Successful: {successful}/{len(results)}")
        logger.info(f"Failed: {failed}/{len(results)}")
        logger.info("")

        # Show individual times
        logger.info("Collector Timings:")
        for name, success, duration in sorted(results, key=lambda x: x[2], reverse=True):
            status = "✓" if success else "✗"
            logger.info(f"  {status} {name:45s} {duration:6.2f}s")

        if failed > 0:
            logger.info("")
            logger.info("Failed collectors:")
            for name, success, _ in results:
                if not success:
                    logger.info(f"  [✗] {name}")

        logger.info("=" * 60)

        return {
            "total_duration_seconds": total_duration,
            "successful": successful,
            "failed": failed,
            "results": [
                {"name": name, "success": success, "duration": duration} for name, success, duration in results
            ],
        }


async def main():
    """Main entry point"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    logger.info("")
    logger.info("Director Observatory - Async Metrics Collection")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    orchestrator = AsyncMetricsOrchestrator()
    summary = await orchestrator.collect_all_metrics()

    logger.info("")
    if summary["failed"] == 0:
        logger.info("[✓] All collectors completed successfully!")
    else:
        logger.info(f"[!] {summary['failed']}/{len(summary['results'])} collectors failed")

    logger.info("")
    logger.info("Next step: Generate dashboards")
    logger.info("  python execution/refresh_all_dashboards.py")
    logger.info("")

    # Exit code: 0 if all succeeded, 1 if any failed
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
