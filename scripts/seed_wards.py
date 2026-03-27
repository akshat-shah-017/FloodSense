#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from psycopg import connect


INSERT_SQL = """
INSERT INTO wards (
    city_id,
    ward_name,
    ward_number,
    boundary,
    area_km2,
    population,
    population_density
)
VALUES (
    %s,
    %s,
    %s,
    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
    %s,
    %s,
    %s
)
ON CONFLICT DO NOTHING
RETURNING ward_id;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load ward GeoJSON into PostGIS.")
    parser.add_argument("geojson_path", help="Path to ward GeoJSON file.")
    parser.add_argument(
        "--target-count",
        type=int,
        default=None,
        help="Optional cap on number of ward rows to seed (default: 250 for city_id=delhi).",
    )
    return parser.parse_args()


def _database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyrus")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def load_geojson(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {path}")

    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    if payload.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON must be a FeatureCollection.")

    return payload


def normalize_geometry(geometry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not geometry:
        return None

    gtype = geometry.get("type")
    if gtype == "Polygon":
        return geometry

    if gtype == "MultiPolygon":
        polygons = geometry.get("coordinates") or []
        if len(polygons) == 1:
            return {"type": "Polygon", "coordinates": polygons[0]}

    return None


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _normalized_properties(props: dict[str, Any]) -> dict[str, Any]:
    return {_normalize_key(str(k)): v for k, v in props.items()}


def _prop(
    props: dict[str, Any],
    *candidates: str,
) -> Any:
    for key in candidates:
        normalized = _normalize_key(key)
        if normalized in props:
            return props[normalized]
    return None


def main() -> int:
    args = parse_args()
    geojson_path = Path(args.geojson_path)
    city_id = os.getenv("CITY_ID", "delhi")
    target_count = args.target_count
    if target_count is None and city_id.lower() == "delhi":
        target_count = 250

    data = load_geojson(geojson_path)
    raw_features = data.get("features", [])

    rows: list[tuple[str, int | None, float | None, int | None, float | None, str]] = []
    skipped = 0
    for feature in raw_features:
        props = _normalized_properties((feature.get("properties") or {}))
        geometry = normalize_geometry(feature.get("geometry"))
        if geometry is None:
            skipped += 1
            continue

        ward_name_raw = _prop(props, "ward_name", "name", "ward")
        ward_name = str(ward_name_raw).strip() if ward_name_raw is not None else ""
        if not ward_name:
            skipped += 1
            continue

        ward_number = parse_int(
            _prop(props, "ward_number", "ward_no", "ward_num", "wardno", "wardid")
        )
        area_km2 = parse_float(_prop(props, "area_km2", "area", "area_sqkm"))
        population = parse_int(_prop(props, "population", "pop_total"))
        population_density = parse_float(
            _prop(props, "population_density", "pop_density", "density")
        )

        rows.append(
            (
                ward_name,
                ward_number,
                area_km2,
                population,
                population_density,
                json.dumps(geometry),
            )
        )

    if target_count is not None and len(rows) > target_count:
        print(
            f"Info: limiting seed rows to first {target_count} wards "
            f"(available valid geometries={len(rows)})."
        )
        rows = rows[:target_count]

    total = len(rows)
    inserted = 0

    print(
        f"Loading {total} ward features from {geojson_path} into city_id='{city_id}' "
        f"(pre-skip count={len(raw_features)}, skipped_invalid={skipped})"
    )

    with connect(_database_dsn()) as conn:
        with conn.cursor() as cur:
            for idx, (ward_name, ward_number, area_km2, population, population_density, geometry_json) in enumerate(rows, start=1):
                cur.execute(
                    INSERT_SQL,
                    (
                        city_id,
                        ward_name,
                        ward_number,
                        geometry_json,
                        area_km2,
                        population,
                        population_density,
                    ),
                )
                row = cur.fetchone()
                if row:
                    inserted += 1
                    print(f"[{idx}/{total}] inserted: {ward_name}")
                else:
                    skipped += 1
                    print(f"[{idx}/{total}] duplicate ignored: {ward_name}")

        conn.commit()

    print(
        "Completed ward seeding "
        f"(total={total}, inserted={inserted}, skipped={skipped})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
