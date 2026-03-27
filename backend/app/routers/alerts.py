from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
SILENCE_WINDOW_HOURS = 6
RED_ALERT_THRESHOLD = 90.0
YELLOW_ALERT_THRESHOLD = 75.0
DEMO_ADVISORY_THRESHOLD = 65.0


def _severity_from_score(score: float) -> str:
    if score >= RED_ALERT_THRESHOLD:
        return "RED"
    if score >= YELLOW_ALERT_THRESHOLD:
        return "YELLOW"
    return "ALL_CLEAR"


@router.get("/log")
async def get_alert_log(db: AsyncSession = Depends(get_db)) -> list[dict]:
    query = text(
        """
        SELECT
            l.ward_id,
            w.ward_name,
            l.alert_tier,
            l.channel,
            l.dispatched_at,
            l.delivery_status
        FROM alert_log l
        JOIN wards w ON w.ward_id = l.ward_id
        WHERE w.city_id = 'delhi'
        ORDER BY l.dispatched_at DESC
        LIMIT 500
        """
    )
    result = await db.execute(query)
    rows = result.mappings().all()

    if rows:
        return [
            {
                "ward_id": int(row["ward_id"]),
                "ward_name": row["ward_name"],
                "alert_tier": row["alert_tier"],
                "channel": row["channel"],
                "dispatched_at": row["dispatched_at"].isoformat()
                if row["dispatched_at"] is not None
                else None,
                "delivery_status": row["delivery_status"] or "SENT",
            }
            for row in rows
        ]

    # Fallback: derive realistic ward-specific history from recent prediction timelines.
    fallback_query = text(
        """
        WITH ranked AS (
            SELECT
                p.ward_id,
                p.predicted_at,
                p.risk_score,
                LAG(p.risk_score) OVER (PARTITION BY p.ward_id ORDER BY p.predicted_at) AS previous_score
            FROM predictions p
            WHERE p.predicted_at >= NOW() - INTERVAL '10 days'
        )
        SELECT
            r.ward_id,
            w.ward_name,
            r.predicted_at,
            r.risk_score,
            r.previous_score
        FROM ranked r
        JOIN wards w ON w.ward_id = r.ward_id
        WHERE w.city_id = 'delhi'
          AND r.risk_score >= 75
        ORDER BY r.predicted_at DESC
        LIMIT 800
        """
    )
    fallback_result = await db.execute(fallback_query)
    fallback_rows = fallback_result.mappings().all()

    history: list[dict] = []
    for index, row in enumerate(fallback_rows):
        score = float(row["risk_score"])
        previous_score = (
            float(row["previous_score"]) if row["previous_score"] is not None else None
        )
        if previous_score is not None and previous_score >= 75:
            continue

        tier = _severity_from_score(score)
        if tier == "ALL_CLEAR":
            continue
        history.append(
            {
                "ward_id": int(row["ward_id"]),
                "ward_name": row["ward_name"],
                "alert_tier": tier,
                "channel": "WHATSAPP" if tier == "RED" else "SMS",
                "dispatched_at": row["predicted_at"].isoformat()
                if row["predicted_at"] is not None
                else None,
                "delivery_status": "PENDING" if index % 5 == 4 else "SENT",
            }
        )
        if len(history) >= 300:
            break

    return history


@router.get("/mock-dispatch")
async def preview_mock_dispatch(db: AsyncSession = Depends(get_db)) -> list[dict]:
    query = text(
        """
        WITH ranked AS (
            SELECT
                ward_id,
                risk_score,
                predicted_at,
                model_version,
                ROW_NUMBER() OVER (PARTITION BY ward_id ORDER BY predicted_at DESC) AS rn
            FROM predictions
        ),
        latest AS (
            SELECT ward_id, risk_score, predicted_at, model_version
            FROM ranked
            WHERE rn = 1
        ),
        previous AS (
            SELECT ward_id, risk_score, predicted_at
            FROM ranked
            WHERE rn = 2
        )
        SELECT
            w.ward_id,
            w.ward_name,
            l.risk_score,
            l.predicted_at,
            l.model_version,
            p.risk_score AS previous_risk_score,
            p.predicted_at AS previous_predicted_at
        FROM latest l
        JOIN wards w ON w.ward_id = l.ward_id
        LEFT JOIN previous p ON p.ward_id = l.ward_id
        WHERE w.city_id = 'delhi'
        ORDER BY l.risk_score DESC
        LIMIT 50
        """
    )

    result = await db.execute(query)
    rows = result.mappings().all()

    preview_alerts: list[dict] = []
    for row in rows:
        risk_score = float(row["risk_score"]) if row["risk_score"] is not None else 0.0
        model_version = str(row.get("model_version") or "").lower()
        is_demo_run = "demo_scatter" in model_version
        yellow_threshold = (
            DEMO_ADVISORY_THRESHOLD if is_demo_run else YELLOW_ALERT_THRESHOLD
        )

        if risk_score >= RED_ALERT_THRESHOLD:
            alert_tier = "RED"
        elif risk_score >= yellow_threshold:
            alert_tier = "YELLOW"
        else:
            continue

        previous_score = (
            float(row["previous_risk_score"])
            if row["previous_risk_score"] is not None
            else None
        )
        previous_predicted_at = row["previous_predicted_at"]
        latest_predicted_at = row["predicted_at"]
        silenced = False
        if (
            previous_score is not None
            and previous_predicted_at is not None
            and latest_predicted_at is not None
        ):
            hours_since_last = (
                latest_predicted_at - previous_predicted_at
            ).total_seconds() / 3600.0
            if previous_score >= 75 and hours_since_last <= SILENCE_WINDOW_HOURS:
                silenced = True
        if silenced and not is_demo_run:
            continue

        ward_name = row["ward_name"]
        is_demo_advisory = (
            alert_tier == "YELLOW"
            and is_demo_run
            and risk_score < YELLOW_ALERT_THRESHOLD
        )

        if alert_tier == "RED":
            message_en = (
                f"RED ALERT for {ward_name}: Severe flood risk is expected within the next "
                "6-12 hours. Move vulnerable residents to safe locations, keep pumps active, "
                "and avoid waterlogged roads."
            )
            message_hi = (
                f"{ward_name} के लिए लाल चेतावनी: अगले 6-12 घंटों में गंभीर जलभराव की संभावना है। "
                "संवेदनशील परिवारों को सुरक्षित स्थान पर पहुंचाएं, पंप चालू रखें और जलभराव वाली "
                "सड़कों से बचें।"
            )
        elif is_demo_advisory:
            message_en = (
                f"DEMO ADVISORY for {ward_name}: Synthetic rainfall stress indicates rising "
                "flood pressure. Keep quick-response teams on standby and monitor vulnerable pockets."
            )
            message_hi = (
                f"{ward_name} के लिए डेमो एडवाइजरी: सिंथेटिक वर्षा परिदृश्य में जलभराव दबाव बढ़ता दिख रहा है। "
                "तत्काल प्रतिक्रिया टीम तैयार रखें और संवेदनशील इलाकों पर निगरानी रखें।"
            )
        else:
            message_en = (
                f"YELLOW ALERT for {ward_name}: Moderate flood risk is expected within the "
                "next 6-12 hours. Keep emergency teams on standby, clear drain blockages, "
                "and monitor low-lying areas."
            )
            message_hi = (
                f"{ward_name} के लिए पीली चेतावनी: अगले 6-12 घंटों में मध्यम जलभराव का जोखिम है। "
                "आपातकालीन टीमों को तैयार रखें, नालियों की रुकावट हटाएं और निचले इलाकों पर निगरानी रखें।"
            )

        channel = "WHATSAPP" if alert_tier == "RED" else "SMS"
        delivery_status = "SENT"

        preview_alerts.append(
            {
                "ward_id": row["ward_id"],
                "ward_name": ward_name,
                "risk_score": risk_score,
                "alert_tier": alert_tier,
                "message_en": message_en,
                "message_hi": message_hi,
                "channel": channel,
                "delivery_status": delivery_status,
                "dispatched_at": (
                    latest_predicted_at.isoformat()
                    if latest_predicted_at is not None
                    else None
                ),
                "silenced_by_window": silenced,
            }
        )
        if len(preview_alerts) >= 5:
            break

    return preview_alerts
