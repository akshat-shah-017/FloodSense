import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PredictionService:
    @staticmethod
    async def get_current_predictions_geojson(
        db: AsyncSession, city_id: str = "delhi"
    ) -> dict:
        """
        Returns a GeoJSON FeatureCollection.
        Each feature = one ward polygon with prediction properties.
        Uses a single SQL query joining predictions (latest per ward) with wards (boundary + name).

        SQL strategy:
        WITH latest AS (
          SELECT DISTINCT ON (ward_id) *
          FROM predictions
          WHERE ward_id IN (SELECT ward_id FROM wards WHERE city_id = :city_id)
          ORDER BY ward_id, predicted_at DESC
        )
        SELECT
          w.ward_id, w.ward_name, w.ward_number,
          ST_AsGeoJSON(w.boundary)::json AS geometry,
          p.risk_score, p.ci_lower, p.ci_upper, p.risk_tier,
          p.shap_feature_1, p.shap_value_1,
          p.shap_feature_2, p.shap_value_2,
          p.shap_feature_3, p.shap_value_3,
          p.source_status, p.predicted_at, p.model_version
        FROM wards w
        LEFT JOIN latest p ON w.ward_id = p.ward_id
        WHERE w.city_id = :city_id

        If a ward has no predictions yet (LEFT JOIN null), set risk_score=0,
        risk_tier='UNKNOWN', source_status='NO_DATA'.

        Build and return a valid GeoJSON FeatureCollection dict (not a string).
        """
        query = text(
            """
            WITH latest AS (
                SELECT DISTINCT ON (ward_id) *
                FROM predictions
                WHERE ward_id IN (SELECT ward_id FROM wards WHERE city_id = :city_id)
                ORDER BY ward_id, predicted_at DESC
            )
            SELECT
                w.ward_id,
                w.ward_name,
                w.ward_number,
                ST_AsGeoJSON(w.boundary)::json AS geometry,
                p.risk_score,
                p.ci_lower,
                p.ci_upper,
                p.risk_tier,
                p.shap_feature_1,
                p.shap_value_1,
                p.shap_feature_2,
                p.shap_value_2,
                p.shap_feature_3,
                p.shap_value_3,
                p.source_status,
                p.predicted_at,
                p.model_version
            FROM wards w
            LEFT JOIN latest p ON w.ward_id = p.ward_id
            WHERE w.city_id = :city_id
            ORDER BY w.ward_id
            """
        )

        result = await db.execute(query, {"city_id": city_id})
        rows = result.mappings().all()

        features: list[dict] = []
        for row in rows:
            geometry = row["geometry"]
            if isinstance(geometry, str):
                geometry = json.loads(geometry)

            has_prediction = row["risk_score"] is not None

            properties = {
                "ward_id": row["ward_id"],
                "ward_name": row["ward_name"],
                "ward_number": row["ward_number"],
                "risk_score": float(row["risk_score"]) if has_prediction else 0.0,
                "ci_lower": float(row["ci_lower"]) if row["ci_lower"] is not None else None,
                "ci_upper": float(row["ci_upper"]) if row["ci_upper"] is not None else None,
                "risk_tier": row["risk_tier"] if has_prediction else "UNKNOWN",
                "shap_feature_1": row["shap_feature_1"],
                "shap_value_1": (
                    float(row["shap_value_1"]) if row["shap_value_1"] is not None else None
                ),
                "shap_feature_2": row["shap_feature_2"],
                "shap_value_2": (
                    float(row["shap_value_2"]) if row["shap_value_2"] is not None else None
                ),
                "shap_feature_3": row["shap_feature_3"],
                "shap_value_3": (
                    float(row["shap_value_3"]) if row["shap_value_3"] is not None else None
                ),
                "source_status": row["source_status"] if has_prediction else "NO_DATA",
                "predicted_at": (
                    row["predicted_at"].isoformat() if row["predicted_at"] is not None else None
                ),
                "model_version": row["model_version"],
            }

            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": properties,
                }
            )

        return {"type": "FeatureCollection", "features": features}

    @staticmethod
    async def get_ward_prediction_detail(db: AsyncSession, ward_id: int) -> dict:
        """
        Returns ward detail for popup.
        Includes: ward_id, ward_name, current risk_score, ci_lower, ci_upper, risk_tier,
        all 3 SHAP feature/value pairs, source_status, predicted_at, model_version.
        Also includes score_history: last 30 days of predictions as
        [{predicted_at: ISO str, risk_score: float}].
        Raise HTTPException(404) if ward_id does not exist.
        """
        ward_query = text(
            """
            SELECT ward_id, ward_name
            FROM wards
            WHERE ward_id = :ward_id
            """
        )
        ward_result = await db.execute(ward_query, {"ward_id": ward_id})
        ward = ward_result.mappings().first()

        if ward is None:
            raise HTTPException(status_code=404, detail="Ward not found")

        latest_query = text(
            """
            SELECT
                ward_id,
                predicted_at,
                risk_score,
                ci_lower,
                ci_upper,
                risk_tier,
                shap_feature_1,
                shap_value_1,
                shap_feature_2,
                shap_value_2,
                shap_feature_3,
                shap_value_3,
                source_status,
                model_version
            FROM predictions
            WHERE ward_id = :ward_id
            ORDER BY predicted_at DESC
            LIMIT 1
            """
        )

        latest_result = await db.execute(latest_query, {"ward_id": ward_id})
        latest = latest_result.mappings().first()

        history_query = text(
            """
            SELECT predicted_at, risk_score
            FROM predictions
            WHERE ward_id = :ward_id
              AND predicted_at >= NOW() - INTERVAL '30 days'
            ORDER BY predicted_at ASC
            """
        )
        history_result = await db.execute(history_query, {"ward_id": ward_id})
        history_rows = history_result.mappings().all()

        score_history = [
            {
                "predicted_at": row["predicted_at"].isoformat(),
                "risk_score": float(row["risk_score"]),
            }
            for row in history_rows
        ]

        if latest is None:
            return {
                "ward_id": ward["ward_id"],
                "ward_name": ward["ward_name"],
                "risk_score": 0.0,
                "ci_lower": None,
                "ci_upper": None,
                "risk_tier": "UNKNOWN",
                "shap_feature_1": None,
                "shap_value_1": None,
                "shap_feature_2": None,
                "shap_value_2": None,
                "shap_feature_3": None,
                "shap_value_3": None,
                "source_status": "NO_DATA",
                "predicted_at": None,
                "model_version": None,
                "score_history": score_history,
            }

        return {
            "ward_id": ward["ward_id"],
            "ward_name": ward["ward_name"],
            "risk_score": float(latest["risk_score"]),
            "ci_lower": float(latest["ci_lower"]) if latest["ci_lower"] is not None else None,
            "ci_upper": float(latest["ci_upper"]) if latest["ci_upper"] is not None else None,
            "risk_tier": latest["risk_tier"],
            "shap_feature_1": latest["shap_feature_1"],
            "shap_value_1": (
                float(latest["shap_value_1"]) if latest["shap_value_1"] is not None else None
            ),
            "shap_feature_2": latest["shap_feature_2"],
            "shap_value_2": (
                float(latest["shap_value_2"]) if latest["shap_value_2"] is not None else None
            ),
            "shap_feature_3": latest["shap_feature_3"],
            "shap_value_3": (
                float(latest["shap_value_3"]) if latest["shap_value_3"] is not None else None
            ),
            "source_status": latest["source_status"],
            "predicted_at": (
                latest["predicted_at"].isoformat()
                if latest["predicted_at"] is not None
                else None
            ),
            "model_version": latest["model_version"],
            "score_history": score_history,
        }

    @staticmethod
    async def write_predictions(
        db: AsyncSession,
        predictions: list[dict],
        city_id: str = "delhi",
    ) -> int:
        """
        Bulk-insert a list of prediction dicts (from predict_all_wards()) into the
        predictions table without using ON CONFLICT.
        Uses one UTC batch timestamp for all rows in this run.
        Deletes any rows for that exact timestamp, then inserts the full batch.
        Returns count of rows inserted.
        """
        if not predictions:
            return 0

        expected_count_query = text(
            """
            SELECT COUNT(*)
            FROM wards
            WHERE city_id = :city_id
            """
        )
        expected_ward_count = int(
            (await db.execute(expected_count_query, {"city_id": city_id})).scalar_one()
        )

        if len(predictions) != expected_ward_count:
            logger.warning(
                "Prediction count mismatch for city_id=%s. expected=%s actual=%s",
                city_id,
                expected_ward_count,
                len(predictions),
            )

        batch_time = datetime.now(timezone.utc)

        risk_tier_constraint_query = text(
            """
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'predictions'
              AND c.conname = 'predictions_risk_tier_check'
              AND pg_get_constraintdef(c.oid) ILIKE '%UNKNOWN%'
            """
        )
        has_unknown_risk_tier = (
            await db.execute(risk_tier_constraint_query)
        ).scalar_one_or_none()
        if has_unknown_risk_tier is None:
            logger.warning(
                "Updating predictions_risk_tier_check to allow UNKNOWN for fallback rows."
            )
            await db.execute(
                text(
                    """
                    ALTER TABLE predictions
                    DROP CONSTRAINT IF EXISTS predictions_risk_tier_check
                    """
                )
            )
            await db.execute(
                text(
                    """
                    ALTER TABLE predictions
                    ADD CONSTRAINT predictions_risk_tier_check
                    CHECK (risk_tier IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'))
                    """
                )
            )

        delete_query = text(
            """
            DELETE FROM predictions
            WHERE predicted_at = :predicted_at
            """
        )

        insert_query = text(
            """
            INSERT INTO predictions (
                ward_id,
                predicted_at,
                risk_score,
                ci_lower,
                ci_upper,
                risk_tier,
                shap_feature_1,
                shap_value_1,
                shap_feature_2,
                shap_value_2,
                shap_feature_3,
                shap_value_3,
                model_version,
                source_status
            ) VALUES (
                :ward_id,
                :predicted_at,
                :risk_score,
                :ci_lower,
                :ci_upper,
                :risk_tier,
                :shap_feature_1,
                :shap_value_1,
                :shap_feature_2,
                :shap_value_2,
                :shap_feature_3,
                :shap_value_3,
                :model_version,
                :source_status
            )
            """
        )

        rows: list[dict] = []
        for prediction in predictions:
            ci_lower = prediction.get("ci_lower")
            ci_upper = prediction.get("ci_upper")
            shap_value_1 = prediction.get("shap_value_1")
            shap_value_2 = prediction.get("shap_value_2")
            shap_value_3 = prediction.get("shap_value_3")
            rows.append(
                {
                    "ward_id": int(prediction["ward_id"]),
                    "predicted_at": batch_time,
                    "risk_score": float(prediction.get("risk_score", 0.0)),
                    "ci_lower": float(ci_lower) if ci_lower is not None else None,
                    "ci_upper": float(ci_upper) if ci_upper is not None else None,
                    "risk_tier": str(prediction.get("risk_tier", "LOW")),
                    "shap_feature_1": prediction.get("shap_feature_1"),
                    "shap_value_1": float(shap_value_1) if shap_value_1 is not None else None,
                    "shap_feature_2": prediction.get("shap_feature_2"),
                    "shap_value_2": float(shap_value_2) if shap_value_2 is not None else None,
                    "shap_feature_3": prediction.get("shap_feature_3"),
                    "shap_value_3": float(shap_value_3) if shap_value_3 is not None else None,
                    "model_version": prediction.get("model_version"),
                    "source_status": prediction.get("source_status", "FRESH"),
                }
            )

        try:
            await db.execute(delete_query, {"predicted_at": batch_time})
            await db.execute(insert_query, rows)

            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return len(rows)
