from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/v1", tags=["predictions"])


@router.get("/predictions/current")
async def get_current_predictions(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    geojson = await PredictionService.get_current_predictions_geojson(db=db)
    return JSONResponse(
        content=geojson,
        media_type="application/geo+json",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/predictions/{ward_id}")
async def get_ward_prediction_detail(
    ward_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await PredictionService.get_ward_prediction_detail(db=db, ward_id=ward_id)


@router.get("/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Returns system-level statistics computed from the predictions table.
    If the table is empty, returns zeros/nulls without raising.
    """
    query = text(
        """
        WITH latest AS (
            SELECT DISTINCT ON (ward_id)
                ward_id, risk_score, risk_tier, source_status, predicted_at
            FROM predictions
            ORDER BY ward_id, predicted_at DESC
        )
        SELECT
            COUNT(*)                                                   AS total_wards,
            MAX(predicted_at)                                          AS last_inference_at,
            ROUND(AVG(risk_score)::numeric, 1)                        AS avg_risk_score,
            SUM(CASE WHEN risk_tier = 'HIGH'    THEN 1 ELSE 0 END)   AS high_count,
            SUM(CASE WHEN risk_tier = 'MEDIUM'  THEN 1 ELSE 0 END)   AS medium_count,
            SUM(CASE WHEN risk_tier = 'LOW'     THEN 1 ELSE 0 END)   AS low_count,
            SUM(CASE WHEN risk_tier = 'UNKNOWN' THEN 1 ELSE 0 END)   AS unknown_count,
            SUM(CASE WHEN source_status != 'FRESH' THEN 1 ELSE 0 END) AS stale_count
        FROM latest
    """
    )

    try:
        result = await db.execute(query)
        row = result.mappings().first()
        if row is None or row["total_wards"] == 0:
            raise ValueError("empty")
        return {
            "total_wards": int(row["total_wards"]),
            "last_inference_at": row["last_inference_at"].isoformat()
            if row["last_inference_at"]
            else None,
            "avg_risk_score": float(row["avg_risk_score"])
            if row["avg_risk_score"] is not None
            else None,
            "risk_distribution": {
                "HIGH": int(row["high_count"]),
                "MEDIUM": int(row["medium_count"]),
                "LOW": int(row["low_count"]),
                "UNKNOWN": int(row["unknown_count"]),
            },
            "wards_with_stale_data": int(row["stale_count"]),
        }
    except Exception:
        return {
            "total_wards": 0,
            "last_inference_at": None,
            "avg_risk_score": None,
            "risk_distribution": {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
            "wards_with_stale_data": 0,
        }
