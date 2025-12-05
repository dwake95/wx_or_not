"""
Dashboard API Endpoints

Provides data for monitoring dashboard:
- System health status
- Verification metrics
- Model performance comparison
- Data freshness indicators
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.database import get_db_connection
from scripts.system_health_check import (
    check_database_connectivity,
    check_data_freshness,
    check_disk_space,
    check_verification_status
)

router = APIRouter()


# Response Models
class HealthStatus(BaseModel):
    """System health status response."""
    overall_status: str
    database: Dict[str, Any]
    data_freshness: Dict[str, Any]
    disk_space: Dict[str, Any]
    verification: Dict[str, Any]
    timestamp: datetime


class VerificationMetrics(BaseModel):
    """Verification metrics for a model."""
    model_name: str
    pairs_count: int
    mae: Optional[float]
    rmse: Optional[float]
    bias: Optional[float]
    csi: Optional[float]
    hit_rate: Optional[float]
    false_alarm_ratio: Optional[float]
    latest_verification: Optional[datetime]


class ModelComparison(BaseModel):
    """Comparison of model performances."""
    gfs: VerificationMetrics
    nam: VerificationMetrics
    winner: str
    win_reason: str


class DataStats(BaseModel):
    """Database statistics."""
    forecast_count: int
    observation_count: int
    verification_count: int
    latest_forecast: Optional[datetime]
    latest_observation: Optional[datetime]
    latest_verification: Optional[datetime]


# Endpoints
@router.get("/health", response_model=HealthStatus)
async def get_health_status():
    """
    Get overall system health status.

    Checks:
    - Database connectivity
    - Data freshness
    - Disk space
    - Verification status
    """
    # Run all health checks
    db_status, db_message = check_database_connectivity()
    fresh_status, fresh_message = check_data_freshness()
    disk_status, disk_message = check_disk_space()
    verify_status, verify_message = check_verification_status()

    # Determine overall status
    all_ok = all([db_status, fresh_status, disk_status, verify_status])
    overall = "healthy" if all_ok else "degraded"

    return HealthStatus(
        overall_status=overall,
        database={
            "status": "pass" if db_status else "fail",
            "message": db_message
        },
        data_freshness={
            "status": "pass" if fresh_status else "fail",
            "message": fresh_message
        },
        disk_space={
            "status": "pass" if disk_status else "fail",
            "message": disk_message
        },
        verification={
            "status": "pass" if verify_status else "fail",
            "message": verify_message
        },
        timestamp=datetime.now(timezone.utc)
    )


@router.get("/metrics/{model_name}", response_model=VerificationMetrics)
async def get_verification_metrics(model_name: str):
    """
    Get verification metrics for a specific model (GFS or NAM).

    Args:
        model_name: Model name ('GFS' or 'NAM')
    """
    model_name = model_name.upper()
    if model_name not in ['GFS', 'NAM']:
        raise HTTPException(status_code=400, detail="Model must be 'GFS' or 'NAM'")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get aggregate metrics from last 7 days
                cur.execute("""
                    SELECT
                        COUNT(*) as pairs,
                        AVG(absolute_error) as avg_mae,
                        SQRT(AVG(squared_error)) as avg_rmse,
                        AVG(error) as avg_bias,
                        MAX(created_at) as latest
                    FROM verification_scores
                    WHERE model_name = %s
                      AND created_at > NOW() - INTERVAL '7 days'
                """, (model_name,))

                result = cur.fetchone()
                pairs, mae, rmse, bias, latest = result if result else (0, None, None, None, None)

                # Get decision metrics if threshold_verification table exists
                try:
                    cur.execute("""
                        SELECT
                            AVG(csi) as avg_csi,
                            AVG(hit_rate) as avg_hit_rate,
                            AVG(false_alarm_ratio) as avg_far
                        FROM threshold_verification
                        WHERE model_name = %s
                          AND created_at > NOW() - INTERVAL '7 days'
                    """, (model_name,))
                    decision_result = cur.fetchone()
                except:
                    decision_result = (None, None, None)

                csi, hit_rate, far = decision_result if decision_result else (None, None, None)

        return VerificationMetrics(
            model_name=model_name,
            pairs_count=pairs or 0,
            mae=float(mae) if mae else None,
            rmse=float(rmse) if rmse else None,
            bias=float(bias) if bias else None,
            csi=float(csi) if csi else None,
            hit_rate=float(hit_rate) if hit_rate else None,
            false_alarm_ratio=float(far) if far else None,
            latest_verification=latest
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/comparison", response_model=ModelComparison)
async def get_model_comparison():
    """
    Compare GFS and NAM model performance.

    Returns metrics for both models and determines winner.
    """
    try:
        gfs_metrics = await get_verification_metrics("GFS")
        nam_metrics = await get_verification_metrics("NAM")

        # Determine winner based on CSI (primary decision metric)
        # If CSI not available, use MAE
        if gfs_metrics.csi and nam_metrics.csi:
            if gfs_metrics.csi > nam_metrics.csi:
                winner = "GFS"
                reason = f"Higher CSI ({gfs_metrics.csi:.3f} vs {nam_metrics.csi:.3f})"
            elif nam_metrics.csi > gfs_metrics.csi:
                winner = "NAM"
                reason = f"Higher CSI ({nam_metrics.csi:.3f} vs {gfs_metrics.csi:.3f})"
            else:
                winner = "TIE"
                reason = "Equal CSI scores"
        elif gfs_metrics.mae and nam_metrics.mae:
            if gfs_metrics.mae < nam_metrics.mae:
                winner = "GFS"
                reason = f"Lower MAE ({gfs_metrics.mae:.1f} vs {nam_metrics.mae:.1f} Pa)"
            elif nam_metrics.mae < gfs_metrics.mae:
                winner = "NAM"
                reason = f"Lower MAE ({nam_metrics.mae:.1f} vs {gfs_metrics.mae:.1f} Pa)"
            else:
                winner = "TIE"
                reason = "Equal MAE scores"
        else:
            winner = "INSUFFICIENT_DATA"
            reason = "Not enough verification data"

        return ModelComparison(
            gfs=gfs_metrics,
            nam=nam_metrics,
            winner=winner,
            win_reason=reason
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison error: {str(e)}")


@router.get("/stats", response_model=DataStats)
async def get_data_stats():
    """
    Get overall database statistics.

    Returns counts and timestamps for forecasts, observations, and verifications.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Forecast stats
                cur.execute("""
                    SELECT COUNT(*), MAX(init_time)
                    FROM model_forecasts
                """)
                forecast_count, latest_forecast = cur.fetchone()

                # Observation stats
                cur.execute("""
                    SELECT COUNT(*), MAX(obs_time)
                    FROM observations
                """)
                obs_count, latest_obs = cur.fetchone()

                # Verification stats
                cur.execute("""
                    SELECT COUNT(*), MAX(created_at)
                    FROM verification_scores
                """)
                verify_count, latest_verify = cur.fetchone()

        return DataStats(
            forecast_count=forecast_count or 0,
            observation_count=obs_count or 0,
            verification_count=verify_count or 0,
            latest_forecast=latest_forecast,
            latest_observation=latest_obs,
            latest_verification=latest_verify
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")


@router.get("/system-info")
async def get_system_info():
    """Get system resource information."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "disk_percent": disk.percent,
            "disk_used_gb": disk.used / (1024**3),
            "disk_free_gb": disk.free / (1024**3),
            "timestamp": datetime.now(timezone.utc)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System info error: {str(e)}")
