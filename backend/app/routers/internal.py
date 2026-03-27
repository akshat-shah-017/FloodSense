import importlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])
logger = logging.getLogger("uvicorn.error")
DEFAULT_INTERNAL_API_SECRET = "vyrus-internal-secret-change-me"


class InternalPredictRequest(BaseModel):
    rainfall_mm: float | None = Field(default=None, ge=0, le=500)
    demo_mode: bool = False


def _is_internal_ip(client_ip: str | None) -> bool:
    if not client_ip:
        return False
    return client_ip.startswith(("172.", "10.", "127.")) or client_ip == "::1"


def _extract_candidate_ips(request: Request) -> list[str]:
    candidates: list[str] = []
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        for token in forwarded_for.split(","):
            ip = token.strip()
            if ip:
                candidates.append(ip)

    if request.client and request.client.host:
        candidates.append(request.client.host)

    return candidates


def _has_valid_internal_secret(request: Request) -> bool:
    configured_secret = os.getenv("INTERNAL_API_SECRET", DEFAULT_INTERNAL_API_SECRET)
    provided_secret = request.headers.get("x-internal-secret")
    return bool(provided_secret) and provided_secret == configured_secret


def _risk_tier_from_score(score: float) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def _scenario_multiplier(rainfall_mm: float) -> float:
    if rainfall_mm >= 200:
        return 1.22
    if rainfall_mm >= 100:
        return 1.14
    if rainfall_mm >= 50:
        return 1.08
    return 1.02


def _apply_rainfall_scenario(
    predictions: list[dict[str, Any]],
    rainfall_mm: float | None,
    demo_mode: bool,
    ward_factor_map: dict[int, dict[str, float]],
) -> list[dict[str, Any]]:
    if rainfall_mm is None and not demo_mode:
        return predictions

    multiplier = _scenario_multiplier(rainfall_mm if rainfall_mm is not None else 60.0)
    adjusted_predictions: list[dict[str, Any]] = []

    for prediction in predictions:
        row = dict(prediction)
        source_status = str(row.get("source_status", "FRESH"))
        if source_status == "NO_DATA" and not demo_mode:
            adjusted_predictions.append(row)
            continue

        base_score = float(row.get("risk_score", 0.0))
        ward_id = int(row.get("ward_id", 0))
        factors = ward_factor_map.get(ward_id, {})
        drainage_risk = float(factors.get("drainage_risk", ((ward_id * 13) % 9) / 10.0))
        topography_risk = float(factors.get("topography_risk", ((ward_id * 17) % 8) / 10.0))
        river_risk = float(factors.get("river_risk", ((ward_id * 19) % 7) / 10.0))
        cluster_offset = (((ward_id * 31) % 21) - 10) / 10.0
        vulnerability = (0.45 * drainage_risk) + (0.35 * topography_risk) + (0.20 * river_risk)
        rainfall_component = (rainfall_mm / 200.0) if rainfall_mm is not None else 0.35
        additive_pressure = (rainfall_component * 8.0) + (vulnerability * 16.0) + (cluster_offset * 3.5)
        if demo_mode:
            additive_pressure += (vulnerability * 7.0) + (cluster_offset * 2.5)
            synthetic_hazard = ((ward_id * 97) % 100) / 100.0
            demo_floor_score = (
                20.0
                + (synthetic_hazard * 55.0)
                + (vulnerability * 18.0)
                + (rainfall_component * 18.0)
                + (cluster_offset * 6.0)
            )
        else:
            demo_floor_score = 0.0

        adjusted_score = max(
            0.0,
            min(100.0, max((base_score * multiplier) + additive_pressure, demo_floor_score)),
        )

        ci_lower = row.get("ci_lower")
        ci_upper = row.get("ci_upper")
        spread_low = base_score - float(ci_lower) if ci_lower is not None else 5.0
        spread_high = float(ci_upper) - base_score if ci_upper is not None else 5.0

        adjusted_ci_lower = max(0.0, adjusted_score - spread_low)
        adjusted_ci_upper = min(100.0, adjusted_score + spread_high)

        row["risk_score"] = round(adjusted_score, 3)
        row["ci_lower"] = round(adjusted_ci_lower, 3)
        row["ci_upper"] = round(adjusted_ci_upper, 3)
        row["risk_tier"] = _risk_tier_from_score(adjusted_score)
        if demo_mode:
            # In demo mode, expose ward-specific explanatory drivers instead of
            # repeating static model SHAP placeholders.
            row["shap_feature_1"] = "rainfall_intensity"
            row["shap_value_1"] = round((rainfall_component * 2.8) + (vulnerability * 1.9), 3)
            row["shap_feature_2"] = "drainage_stress"
            row["shap_value_2"] = round(((drainage_risk - 0.5) * 3.2) + (cluster_offset * 0.35), 3)
            row["shap_feature_3"] = "river_proximity"
            row["shap_value_3"] = round(((river_risk - 0.5) * 2.8) + (cluster_offset * 0.4), 3)
        if source_status == "NO_DATA" and demo_mode:
            row["source_status"] = "DEGRADED"
        model_version = str(row.get("model_version", ""))
        mode_suffix = "demo_scatter" if demo_mode else "scenario"
        scenario_suffix = (
            f"{mode_suffix}_rain_{int(round(rainfall_mm))}mm"
            if rainfall_mm is not None
            else mode_suffix
        )
        row["model_version"] = f"{model_version}|{scenario_suffix}" if model_version else scenario_suffix
        adjusted_predictions.append(row)

    return adjusted_predictions


async def _load_ward_factor_map(db: AsyncSession, city_id: str) -> dict[int, dict[str, float]]:
    query = text(
        """
        WITH latest_features AS (
            SELECT DISTINCT ON (wf.ward_id)
                wf.ward_id,
                wf.drain_density,
                wf.twi_mean,
                wf.dist_river_km
            FROM ward_features wf
            JOIN wards w ON w.ward_id = wf.ward_id
            WHERE w.city_id = :city_id
            ORDER BY wf.ward_id, wf.computed_at DESC
        )
        SELECT
            w.ward_id,
            lf.drain_density,
            lf.twi_mean,
            lf.dist_river_km
        FROM wards w
        LEFT JOIN latest_features lf ON lf.ward_id = w.ward_id
        WHERE w.city_id = :city_id
        ORDER BY w.ward_id
        """
    )
    result = await db.execute(query, {"city_id": city_id})
    rows = result.mappings().all()

    if not rows:
        return {}

    drainage_values = [float(row["drain_density"]) for row in rows if row["drain_density"] is not None]
    twi_values = [float(row["twi_mean"]) for row in rows if row["twi_mean"] is not None]
    river_values = [float(row["dist_river_km"]) for row in rows if row["dist_river_km"] is not None]

    def _normalize(value: float | None, values: list[float], reverse: bool = False) -> float:
        if value is None or not values:
            return 0.5
        low = min(values)
        high = max(values)
        if abs(high - low) < 1e-6:
            return 0.5
        norm = (float(value) - low) / (high - low)
        return 1.0 - norm if reverse else norm

    factor_map: dict[int, dict[str, float]] = {}
    for row in rows:
        ward_id = int(row["ward_id"])
        drain_density = float(row["drain_density"]) if row["drain_density"] is not None else None
        twi_mean = float(row["twi_mean"]) if row["twi_mean"] is not None else None
        dist_river_km = float(row["dist_river_km"]) if row["dist_river_km"] is not None else None
        factor_map[ward_id] = {
            "drainage_risk": _normalize(drain_density, drainage_values, reverse=True),
            "topography_risk": _normalize(twi_mean, twi_values, reverse=False),
            "river_risk": _normalize(dist_river_km, river_values, reverse=True),
        }

    return factor_map


@router.post("/predict")
async def run_internal_prediction(
    request: Request,
    payload: InternalPredictRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not _has_valid_internal_secret(request):
        candidate_ips = _extract_candidate_ips(request)
        if not any(_is_internal_ip(ip) for ip in candidate_ips):
            raise HTTPException(status_code=403, detail="Internal endpoint only")

    city_id = "delhi"

    try:
        predictor_module = importlib.import_module("ml.inference.predictor")
        predict_all_wards = getattr(predictor_module, "predict_all_wards")

        predictions = predict_all_wards(city_id=city_id)
        rainfall_mm = payload.rainfall_mm if payload else None
        demo_mode = payload.demo_mode if payload else False
        logger.info(
            "internal.predict received payload: rainfall_mm=%s demo_mode=%s",
            rainfall_mm,
            demo_mode,
        )
        ward_factor_map = await _load_ward_factor_map(db, city_id)
        predictions = _apply_rainfall_scenario(
            predictions,
            rainfall_mm,
            demo_mode,
            ward_factor_map,
        )
        unique_scores = len({round(float(item.get("risk_score", 0.0)), 2) for item in predictions})
        logger.info(
            "internal.predict adjusted predictions: total=%d unique_scores=%d demo_mode=%s",
            len(predictions),
            unique_scores,
            demo_mode,
        )
        inserted_count = await PredictionService.write_predictions(
            db=db,
            predictions=predictions,
            city_id=city_id,
        )

        return {
            "wards_predicted": inserted_count,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "scenario_applied": rainfall_mm is not None or demo_mode,
            "rainfall_mm": rainfall_mm,
            "demo_mode": demo_mode,
        }
    except Exception as exc:
        logger.exception("Failed to run internal prediction")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
