#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from psycopg import connect


def _database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyrus")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def _default_labels_path() -> Path:
    env_value = os.getenv("FLOOD_LABELS_CSV_PATH")
    if env_value:
        return Path(env_value)

    docker_default = Path("/app/data/indofloods_labels.csv")
    if docker_default.parent.exists():
        return docker_default

    return Path(__file__).resolve().parents[1] / "data" / "indofloods_labels.csv"


def _ensure_synthetic_wards(cur, city_id: str, target_count: int = 250) -> list[int]:
    cur.execute("SELECT ward_id FROM wards WHERE city_id = %s ORDER BY ward_id;", (city_id,))
    ward_ids = [row[0] for row in cur.fetchall()]
    if len(ward_ids) >= target_count:
        return ward_ids[:target_count]

    start_idx = len(ward_ids)
    to_create = target_count - len(ward_ids)
    cols = 25
    base_lat = 28.40
    base_lon = 76.80
    step = 0.02

    for i in range(to_create):
        idx = start_idx + i
        row = idx // cols
        col = idx % cols
        lat0 = base_lat + (row * step)
        lon0 = base_lon + (col * step)
        lat1 = lat0 + (step * 0.9)
        lon1 = lon0 + (step * 0.9)
        wkt = (
            f"POLYGON(({lon0} {lat0}, {lon1} {lat0}, {lon1} {lat1}, "
            f"{lon0} {lat1}, {lon0} {lat0}))"
        )
        cur.execute(
            """
            INSERT INTO wards (
                city_id, ward_name, ward_number, boundary, area_km2, population, population_density
            )
            VALUES (
                %s, %s, %s, ST_SetSRID(ST_GeomFromText(%s), 4326), %s, %s, %s
            )
            RETURNING ward_id;
            """,
            (
                city_id,
                f"Synthetic Ward {idx + 1}",
                idx + 1,
                wkt,
                3.5 + random.random() * 2.0,
                30000 + int(random.random() * 80000),
                7000 + random.random() * 9000,
            ),
        )
        ward_ids.append(cur.fetchone()[0])

    return ward_ids


def _daterange(start: date, end: date, step_days: int = 7):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=step_days)


def main() -> int:
    random.seed(42)
    city_id = os.getenv("CITY_ID", "delhi")
    labels_path = _default_labels_path()
    labels_path.parent.mkdir(parents=True, exist_ok=True)

    start_date = date(2005, 1, 1)
    end_date = date(2023, 12, 31)

    with connect(_database_dsn()) as conn:
        with conn.cursor() as cur:
            ward_ids = _ensure_synthetic_wards(cur, city_id=city_id, target_count=250)
            conn.commit()

            cur.execute(
                """
                DELETE FROM ward_features
                WHERE ward_id IN (
                    SELECT ward_id FROM wards WHERE city_id = %s
                )
                  AND computed_at >= %s
                  AND computed_at < %s;
                """,
                (city_id, datetime(2005, 1, 1), datetime(2024, 1, 1)),
            )
            conn.commit()

            rows = []
            labels = []
            for ward_id in ward_ids:
                ward_bias = random.uniform(-0.2, 0.2)
                impervious = 35 + random.random() * 50
                drain_density = 1.2 + random.random() * 3.5
                dist_river = 0.5 + random.random() * 12.0
                pop_density = 7000 + random.random() * 9000
                flood_freq = 0.4 + random.random() * 5.0
                twi_mean = 7 + random.random() * 8

                for day in _daterange(start_date, end_date, step_days=7):
                    monsoon = 1 if day.month in (7, 8, 9) else 0
                    precip_obs = max(0.0, random.gauss(24 if monsoon else 5, 10))
                    precip_rt = max(0.0, random.gauss(18 if monsoon else 4, 9))

                    spi_1 = random.gauss(1.2 if monsoon else -0.2, 0.9)
                    spi_3 = random.gauss(0.9 if monsoon else -0.1, 0.7)
                    spi_7 = random.gauss(0.7 if monsoon else 0.0, 0.6)

                    risk_signal = (
                        0.018 * precip_rt
                        + 0.013 * precip_obs
                        + 0.25 * spi_1
                        + 0.12 * spi_3
                        + 0.08 * spi_7
                        + 0.006 * impervious
                        - 0.08 * drain_density
                        - 0.03 * dist_river
                        + 0.00004 * pop_density
                        + 0.18 * flood_freq
                        + ward_bias
                        + random.gauss(0, 0.45)
                    )
                    label = 1 if risk_signal > 1.65 else 0

                    ts = datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)
                    rows.append(
                        (
                            ward_id,
                            ts,
                            spi_1,
                            spi_3,
                            spi_7,
                            twi_mean,
                            impervious,
                            drain_density,
                            dist_river,
                            pop_density,
                            flood_freq,
                            precip_rt,
                            precip_obs,
                            "FRESH",
                        )
                    )
                    labels.append((ward_id, day.isoformat(), label))

                    if len(rows) >= 5000:
                        cur.executemany(
                            """
                            INSERT INTO ward_features (
                                ward_id, computed_at, spi_1, spi_3, spi_7, twi_mean,
                                impervious_pct, drain_density, dist_river_km, population_density,
                                flood_freq_10yr, precip_realtime, precip_observed, source_status
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s,
                                %s, %s, %s, %s
                            );
                            """,
                            rows,
                        )
                        conn.commit()
                        rows.clear()

            if rows:
                cur.executemany(
                    """
                    INSERT INTO ward_features (
                        ward_id, computed_at, spi_1, spi_3, spi_7, twi_mean,
                        impervious_pct, drain_density, dist_river_km, population_density,
                        flood_freq_10yr, precip_realtime, precip_observed, source_status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    );
                    """,
                    rows,
                )
                conn.commit()

    with labels_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["ward_id", "date", "label"])
        writer.writerows(labels)

    print(
        f"Seed complete: ward_features rows={len(labels)}, labels_csv='{labels_path}', city_id='{city_id}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
