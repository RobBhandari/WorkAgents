"""
FastAPI Application - Engineering Metrics REST API

Provides programmatic access to quality, security, and flow metrics.

Usage:
    # Development
    uvicorn execution.api.app:app --reload --port 8000

    # Production
    uvicorn execution.api.app:app --host 0.0.0.0 --port 8000 --workers 4

API Documentation:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from execution.api.middleware import (
    CacheControlMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)
from execution.core import get_logger, setup_logging, setup_observability

# Initialize logging and observability
setup_logging(level="INFO", json_output=False)
setup_observability(environment="production", enable_sentry=False, enable_slack=False)

logger = get_logger(__name__)

# Security
security = HTTPBasic()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Engineering Metrics Platform API",
        description="Programmatic access to quality, security, and flow metrics with ML predictions",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add middleware (order matters - last added is executed first)
    app.add_middleware(CacheControlMiddleware)  # Cache headers (innermost)
    app.add_middleware(RequestIDMiddleware)  # Request tracking
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60, requests_per_hour=1000)  # Rate limiting (outermost)

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        logger.info("Engineering Metrics API starting up")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Engineering Metrics API shutting down")

    # ============================================================
    # Authentication
    # ============================================================

    def verify_credentials(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
        """
        Verify HTTP Basic authentication credentials.

        For production, replace with proper authentication:
        - OAuth2/JWT tokens
        - API keys
        - Integration with your identity provider
        """
        import secrets

        from execution.secure_config import ConfigurationError, get_config

        # Get credentials from secure config
        try:
            api_auth = get_config().get_api_auth_config()
            correct_username = api_auth.username
            correct_password = api_auth.password
        except ConfigurationError as e:
            logger.error("API authentication not configured", extra={"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API authentication not configured",
            )

        is_correct_username = secrets.compare_digest(credentials.username, correct_username)
        is_correct_password = secrets.compare_digest(credentials.password, correct_password)

        if not (is_correct_username and is_correct_password):
            logger.warning("Authentication failed", extra={"username": credentials.username, "ip": "unknown"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )

        username: str = credentials.username
        return username

    # ============================================================
    # Health Check
    # ============================================================

    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint for monitoring.

        Returns:
            Status of the API and data freshness
        """
        from execution.core import check_data_freshness

        observatory_dir = Path(".tmp/observatory")

        # Check data freshness
        quality_file = observatory_dir / "quality_history.json"
        security_file = observatory_dir / "security_history.json"
        flow_file = observatory_dir / "flow_history.json"

        health_status: dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
            "data_freshness": {},
        }

        for name, file_path in [("quality", quality_file), ("security", security_file), ("flow", flow_file)]:
            if file_path.exists():
                is_fresh, age_hours = check_data_freshness(file_path, max_age_hours=25.0)
                health_status["data_freshness"][name] = {"fresh": is_fresh, "age_hours": round(age_hours, 2)}
            else:
                health_status["data_freshness"][name] = {"fresh": False, "age_hours": None, "error": "File not found"}

        # Overall health is unhealthy if any data is stale
        if any(not data.get("fresh", False) for data in health_status["data_freshness"].values()):
            health_status["status"] = "degraded"

        status_code = 200 if health_status["status"] == "healthy" else 503

        return JSONResponse(content=health_status, status_code=status_code)

    # ============================================================
    # Quality Metrics Endpoints
    # ============================================================

    @app.get("/api/v1/metrics/quality/latest", tags=["Quality Metrics"])
    async def get_latest_quality_metrics(username: str = Depends(verify_credentials)):
        """
        Get latest quality metrics.

        Returns:
            Latest quality metrics including open bugs, closure rate, etc.
        """
        from execution.collectors.ado_quality_loader import ADOQualityLoader

        try:
            loader = ADOQualityLoader()
            metrics = loader.load_latest_metrics()

            logger.info("Quality metrics accessed", extra={"username": username, "project": metrics.project})

            return {
                "timestamp": metrics.timestamp.isoformat(),
                "project": metrics.project,
                "open_bugs": metrics.open_bugs,
                "closed_this_week": metrics.closed_this_week,
                "net_change": metrics.net_change,
                "closure_rate": metrics.closure_rate,
                "p1_count": metrics.p1_count,
                "p2_count": metrics.p2_count,
            }
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Quality metrics data not found. Run collectors first."
            )
        except Exception as e:
            logger.error("Failed to load quality metrics", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load metrics: {str(e)}"
            )

    @app.get("/api/v1/metrics/quality/history", tags=["Quality Metrics"])
    async def get_quality_history(weeks: int = 12, username: str = Depends(verify_credentials)):
        """
        Get historical quality metrics.

        Args:
            weeks: Number of weeks to return (default: 12)

        Returns:
            Time series of quality metrics
        """
        import json

        history_file = Path(".tmp/observatory/quality_history.json")

        if not history_file.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality history not found")

        try:
            with open(history_file, encoding="utf-8") as f:
                data = json.load(f)

            # Return last N weeks
            weeks_data = data.get("weeks", [])[-weeks:]

            logger.info(
                "Quality history accessed",
                extra={"username": username, "weeks_requested": weeks, "weeks_returned": len(weeks_data)},
            )

            return {"weeks": weeks_data, "count": len(weeks_data)}
        except Exception as e:
            logger.error("Failed to load quality history", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load history: {str(e)}"
            )

    # ============================================================
    # Security Metrics Endpoints
    # ============================================================

    @app.get("/api/v1/metrics/security/latest", tags=["Security Metrics"])
    async def get_latest_security_metrics(username: str = Depends(verify_credentials)):
        """
        Get latest security metrics across all products.

        Returns:
            Latest vulnerability counts by severity
        """
        from execution.collectors.armorcode_loader import ArmorCodeLoader

        try:
            loader = ArmorCodeLoader()
            metrics_by_product = loader.load_latest_metrics()

            # Aggregate across products
            total_vulns = sum(m.total_vulnerabilities for m in metrics_by_product.values())
            total_critical = sum(m.critical for m in metrics_by_product.values())
            total_high = sum(m.high for m in metrics_by_product.values())

            logger.info(
                "Security metrics accessed", extra={"username": username, "product_count": len(metrics_by_product)}
            )

            return {
                "timestamp": datetime.now().isoformat(),
                "total_vulnerabilities": total_vulns,
                "critical": total_critical,
                "high": total_high,
                "product_count": len(metrics_by_product),
                "products": [
                    {
                        "name": name,
                        "total": m.total_vulnerabilities,
                        "critical": m.critical,
                        "high": m.high,
                    }
                    for name, m in metrics_by_product.items()
                ],
            }
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Security metrics data not found. Run collectors first."
            )
        except Exception as e:
            logger.error("Failed to load security metrics", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load metrics: {str(e)}"
            )

    @app.get("/api/v1/metrics/security/product/{product_name}", tags=["Security Metrics"])
    async def get_product_security_metrics(product_name: str, username: str = Depends(verify_credentials)):
        """
        Get security metrics for a specific product.

        Args:
            product_name: Name of the product

        Returns:
            Vulnerability counts for the specified product
        """
        from execution.collectors.armorcode_loader import ArmorCodeLoader

        try:
            loader = ArmorCodeLoader()
            metrics_by_product = loader.load_latest_metrics()

            if product_name not in metrics_by_product:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{product_name}' not found")

            metrics = metrics_by_product[product_name]

            logger.info("Product security metrics accessed", extra={"username": username, "product": product_name})

            return {
                "timestamp": metrics.timestamp.isoformat(),
                "product": product_name,
                "total_vulnerabilities": metrics.total_vulnerabilities,
                "critical": metrics.critical,
                "high": metrics.high,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to load product security metrics", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load metrics: {str(e)}"
            )

    # ============================================================
    # Flow Metrics Endpoints
    # ============================================================

    @app.get("/api/v1/metrics/flow/latest", tags=["Flow Metrics"])
    async def get_latest_flow_metrics(username: str = Depends(verify_credentials)):
        """
        Get latest flow metrics (cycle time, lead time).

        Returns:
            Latest flow metrics with percentiles
        """
        from execution.collectors.ado_flow_loader import ADOFlowLoader

        try:
            loader = ADOFlowLoader()
            metrics = loader.load_latest_metrics()

            logger.info("Flow metrics accessed", extra={"username": username, "project": metrics.project})

            return {
                "timestamp": metrics.timestamp.isoformat(),
                "project": metrics.project,
                "cycle_time_p50": metrics.cycle_time_p50,
                "cycle_time_p85": metrics.cycle_time_p85,
                "cycle_time_p95": metrics.cycle_time_p95,
                "lead_time_p50": metrics.lead_time_p50,
                "lead_time_p85": metrics.lead_time_p85,
                "lead_time_p95": metrics.lead_time_p95,
                "work_items_completed": metrics.throughput,
            }
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Flow metrics data not found. Run collectors first."
            )
        except Exception as e:
            logger.error("Failed to load flow metrics", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load metrics: {str(e)}"
            )

    # ============================================================
    # ML Predictions Endpoints
    # ============================================================

    @app.get("/api/v1/predictions/quality/{project_key}", tags=["ML Predictions"])
    async def predict_quality_trends(
        project_key: str, weeks_ahead: int = 4, username: str = Depends(verify_credentials)
    ):
        """
        Predict bug trends using machine learning.

        Args:
            project_key: Project identifier (e.g., "One_Office")
            weeks_ahead: Number of weeks to predict (1-8, default: 4)

        Returns:
            Predictions, anomalies, and trend analysis
        """
        from execution.ml import TrendPredictor

        # Validate input
        if weeks_ahead < 1 or weeks_ahead > 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weeks_ahead must be between 1 and 8")

        try:
            predictor = TrendPredictor()
            analysis = predictor.predict_trends(project_key, weeks_ahead=weeks_ahead)

            logger.info(
                "Quality predictions generated",
                extra={
                    "username": username,
                    "project": project_key,
                    "weeks_ahead": weeks_ahead,
                    "trend": analysis.trend_direction,
                },
            )

            return {
                "project_key": analysis.project_key,
                "current_bug_count": analysis.current_count,
                "trend_direction": analysis.trend_direction,
                "model_r2_score": round(analysis.model_r2_score, 3),
                "prediction_date": analysis.prediction_date,
                "predictions": [
                    {
                        "week_ending": pred.week_ending,
                        "predicted_count": pred.predicted_count,
                        "confidence_interval": {
                            "lower": pred.confidence_interval[0],
                            "upper": pred.confidence_interval[1],
                        },
                        "anomaly_expected": pred.is_anomaly_expected,
                    }
                    for pred in analysis.predictions
                ],
                "historical_anomalies": analysis.anomalies_detected,
            }
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Quality history data not found. Run collectors first."
            )
        except ValueError as e:
            if "No data found for project" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project '{project_key}' not found in quality history",
                )
            elif "Insufficient data" in str(e):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Prediction failed: {str(e)}")
        except Exception as e:
            logger.error("Failed to generate predictions", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction failed: {str(e)}"
            )

    # ============================================================
    # Dashboard Endpoints
    # ============================================================

    @app.get("/api/v1/dashboards/list", tags=["Dashboards"])
    async def list_dashboards(username: str = Depends(verify_credentials)):
        """
        List available dashboards.

        Returns:
            List of available dashboard files with metadata
        """
        dashboard_dir = Path(".tmp/observatory/dashboards")

        if not dashboard_dir.exists():
            return {"dashboards": [], "count": 0}

        dashboards = []
        for html_file in dashboard_dir.glob("*.html"):
            stat = html_file.stat()
            dashboards.append(
                {
                    "name": html_file.stem,
                    "filename": html_file.name,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        logger.info("Dashboards listed", extra={"username": username, "count": len(dashboards)})

        return {"dashboards": dashboards, "count": len(dashboards)}

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("Engineering Metrics Platform API")
    logger.info("=" * 60)
    logger.info("Starting server...")
    logger.info("API Docs: http://localhost:8000/docs")
    logger.info("Health Check: http://localhost:8000/health")
    logger.info("=" * 60)

    uvicorn.run("execution.api.app:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
