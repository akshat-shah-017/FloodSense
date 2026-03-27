from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import geopandas as gpd
import pandas as pd
from prefect import get_run_logger, task
from shapely.geometry import LineString, Polygon

from tasks.feature_engineering import get_db_connection, http_post_form, log_pipeline_note


DEFAULT_OVERPASS_QUERY = (
    '[out:json]; area["name"="Delhi"]; '
    '(way["waterway"](area); relation["landuse"](area); way["landuse"](area);); out geom;'
)

IMPERVIOUS_LANDUSE = {"commercial", "residential", "industrial"}


def _element_to_geometry(element: dict[str, Any]):
    coords = element.get("geometry") or []
    if not coords:
        return None

    points = [(float(p["lon"]), float(p["lat"])) for p in coords if "lon" in p and "lat" in p]
    if len(points) < 2:
        return None

    tags = element.get("tags") or {}
    if "waterway" in tags:
        return LineString(points)

    if points[0] != points[-1]:
        points.append(points[0])
    if len(points) < 4:
        return None
    return Polygon(points)


def _extract_overpass_geodataframes(payload: dict[str, Any]) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    landuse_rows: list[dict[str, Any]] = []
    drain_rows: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        geom = _element_to_geometry(element)
        if geom is None:
            continue

        landuse = tags.get("landuse")
        if landuse:
            landuse_rows.append({"landuse": landuse, "geometry": geom})

        if tags.get("waterway"):
            drain_rows.append({"waterway": tags.get("waterway"), "geometry": geom})

    landuse_gdf = gpd.GeoDataFrame(landuse_rows, geometry="geometry", crs="EPSG:4326")
    drain_gdf = gpd.GeoDataFrame(drain_rows, geometry="geometry", crs="EPSG:4326")
    return landuse_gdf, drain_gdf


@task(name="fetch_osm_drainage")
def fetch_osm_drainage() -> dict[str, Any]:
    logger = get_run_logger()
    overpass_url = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    query = os.getenv("OSM_OVERPASS_QUERY", DEFAULT_OVERPASS_QUERY)
    payload = http_post_form(overpass_url, {"data": query})
    logger.info("Fetched OSM payload with %d elements.", len(payload.get("elements", [])))
    return payload


@task(name="compute_impervious_pct")
def compute_impervious_pct(osm_payload: dict[str, Any]) -> pd.DataFrame:
    logger = get_run_logger()
    landuse_gdf, _ = _extract_overpass_geodataframes(osm_payload)
    if landuse_gdf.empty:
        logger.warning("No land-use features returned from OSM.")

    landuse_gdf = landuse_gdf[landuse_gdf["landuse"].isin(IMPERVIOUS_LANDUSE)]
    with get_db_connection() as conn:
        wards = gpd.read_postgis(
            "SELECT ward_id, boundary, area_km2 FROM wards",
            conn,
            geom_col="boundary",
        )

    if wards.empty:
        raise RuntimeError("No wards available for OSM impervious calculation.")

    wards_proj = wards.to_crs("EPSG:3857")
    landuse_proj = landuse_gdf.to_crs("EPSG:3857") if not landuse_gdf.empty else landuse_gdf

    records: list[dict[str, float | int]] = []
    for ward in wards_proj.itertuples(index=False):
        ward_geom = ward.boundary
        ward_area_km2 = float(ward.area_km2) if ward.area_km2 else float(ward_geom.area / 1_000_000.0)
        if ward_area_km2 <= 0:
            records.append({"ward_id": int(ward.ward_id), "impervious_pct": 0.0})
            continue

        impervious_area_m2 = 0.0
        if not landuse_proj.empty:
            possible = landuse_proj[landuse_proj.intersects(ward_geom)]
            for poly in possible.geometry:
                inter = poly.intersection(ward_geom)
                if not inter.is_empty:
                    impervious_area_m2 += float(inter.area)

        impervious_km2 = impervious_area_m2 / 1_000_000.0
        impervious_pct = (impervious_km2 / ward_area_km2) * 100.0
        records.append({"ward_id": int(ward.ward_id), "impervious_pct": impervious_pct})

    result = pd.DataFrame(records)
    logger.info("Computed impervious surface percentages for %d wards.", len(result))
    return result


@task(name="compute_drain_density")
def compute_drain_density(osm_payload: dict[str, Any]) -> pd.DataFrame:
    logger = get_run_logger()
    _, drain_gdf = _extract_overpass_geodataframes(osm_payload)
    if drain_gdf.empty:
        logger.warning("No drainage network features returned from OSM.")

    with get_db_connection() as conn:
        wards = gpd.read_postgis(
            "SELECT ward_id, boundary, area_km2 FROM wards",
            conn,
            geom_col="boundary",
        )
    if wards.empty:
        raise RuntimeError("No wards available for drainage density calculation.")

    wards_proj = wards.to_crs("EPSG:3857")
    drains_proj = drain_gdf.to_crs("EPSG:3857") if not drain_gdf.empty else drain_gdf

    records: list[dict[str, float | int]] = []
    for ward in wards_proj.itertuples(index=False):
        ward_geom = ward.boundary
        ward_area_km2 = float(ward.area_km2) if ward.area_km2 else float(ward_geom.area / 1_000_000.0)
        if ward_area_km2 <= 0:
            records.append({"ward_id": int(ward.ward_id), "drain_density": 0.0})
            continue

        total_length_m = 0.0
        if not drains_proj.empty:
            possible = drains_proj[drains_proj.intersects(ward_geom)]
            for line in possible.geometry:
                inter = line.intersection(ward_geom)
                if not inter.is_empty:
                    total_length_m += float(inter.length)

        density = (total_length_m / 1000.0) / ward_area_km2
        records.append({"ward_id": int(ward.ward_id), "drain_density": density})

    result = pd.DataFrame(records)
    logger.info("Computed drainage density for %d wards.", len(result))
    return result


@task(name="flag_changed_wards")
def flag_changed_wards(
    impervious_df: pd.DataFrame,
    drain_density_df: pd.DataFrame,
) -> int:
    logger = get_run_logger()
    now_ts = datetime.now(timezone.utc)
    merged = impervious_df.merge(drain_density_df, on="ward_id", how="outer").fillna(0.0)
    changed_count = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE wards ADD COLUMN IF NOT EXISTS needs_retrain BOOLEAN DEFAULT FALSE;"
            )

            for row in merged.itertuples(index=False):
                ward_id = int(row.ward_id)
                impervious_pct = float(row.impervious_pct)
                drain_density = float(row.drain_density)

                cur.execute(
                    """
                    SELECT impervious_pct
                    FROM ward_features
                    WHERE ward_id = %s
                    ORDER BY computed_at DESC
                    LIMIT 1;
                    """,
                    (ward_id,),
                )
                prev = cur.fetchone()
                prev_impervious = float(prev[0]) if prev and prev[0] is not None else None

                cur.execute(
                    """
                    INSERT INTO ward_features (
                        ward_id, computed_at, impervious_pct, drain_density, source_status
                    )
                    VALUES (%s, %s, %s, %s, 'FRESH');
                    """,
                    (ward_id, now_ts, impervious_pct, drain_density),
                )

                if prev_impervious is not None and abs(impervious_pct - prev_impervious) > 5.0:
                    cur.execute(
                        "UPDATE wards SET needs_retrain = TRUE WHERE ward_id = %s;",
                        (ward_id,),
                    )
                    changed_count += 1

        conn.commit()

    log_pipeline_note(
        flow_name="osm_land_use_retrain_flag",
        status="COMPLETE",
        message=f"Wards marked for retrain due to >5% impervious change: {changed_count}",
    )
    logger.info("flag_changed_wards complete. changed_count=%d", changed_count)
    return changed_count
