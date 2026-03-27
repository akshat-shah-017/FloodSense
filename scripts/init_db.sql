-- FloodSense Phase 2: PostGIS schema + partitioning setup

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS btree_gin;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_partman;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'pg_partman not available in this Postgres image. Continuing without automatic partition maintenance.';
END
$$;

CREATE SCHEMA IF NOT EXISTS archive;

CREATE TABLE IF NOT EXISTS wards (
    ward_id SERIAL PRIMARY KEY,
    city_id VARCHAR(20) NOT NULL DEFAULT 'delhi',
    ward_name VARCHAR(100) NOT NULL,
    ward_number INTEGER,
    boundary GEOMETRY(POLYGON, 4326) NOT NULL,
    centroid GEOMETRY(POINT, 4326)
        GENERATED ALWAYS AS (ST_Centroid(boundary)) STORED,
    area_km2 FLOAT,
    population INTEGER,
    population_density FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT wards_city_ward_name_key UNIQUE (city_id, ward_name)
);

CREATE INDEX IF NOT EXISTS wards_boundary_gix
    ON wards USING GIST (boundary);
CREATE INDEX IF NOT EXISTS wards_city_ward_number_idx
    ON wards (city_id, ward_number);

CREATE TABLE IF NOT EXISTS ward_features (
    id BIGSERIAL,
    ward_id INTEGER REFERENCES wards(ward_id),
    computed_at TIMESTAMPTZ NOT NULL,
    spi_1 FLOAT,
    spi_3 FLOAT,
    spi_7 FLOAT,
    twi_mean FLOAT,
    impervious_pct FLOAT,
    drain_density FLOAT,
    dist_river_km FLOAT,
    population_density FLOAT,
    flood_freq_10yr FLOAT,
    precip_realtime FLOAT,
    precip_observed FLOAT,
    source_status VARCHAR(20) DEFAULT 'FRESH',
    PRIMARY KEY (id, computed_at),
    CONSTRAINT ward_features_source_status_check
        CHECK (source_status IN ('FRESH', 'STALE', 'DEGRADED'))
) PARTITION BY RANGE (computed_at);

CREATE INDEX IF NOT EXISTS ward_features_ward_computed_at_idx
    ON ward_features (ward_id, computed_at DESC);

CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL,
    ward_id INTEGER REFERENCES wards(ward_id),
    predicted_at TIMESTAMPTZ NOT NULL,
    risk_score FLOAT NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    ci_lower FLOAT,
    ci_upper FLOAT,
    risk_tier VARCHAR(10) NOT NULL,
    shap_feature_1 VARCHAR(50),
    shap_value_1 FLOAT,
    shap_feature_2 VARCHAR(50),
    shap_value_2 FLOAT,
    shap_feature_3 VARCHAR(50),
    shap_value_3 FLOAT,
    shap_feature_4 VARCHAR(50),
    shap_value_4 FLOAT,
    shap_feature_5 VARCHAR(50),
    shap_value_5 FLOAT,
    model_version VARCHAR(50),
    PRIMARY KEY (id, predicted_at),
    CONSTRAINT predictions_risk_tier_check
        CHECK (risk_tier IN ('HIGH', 'MEDIUM', 'LOW'))
) PARTITION BY RANGE (predicted_at);

CREATE INDEX IF NOT EXISTS predictions_ward_predicted_at_idx
    ON predictions (ward_id, predicted_at DESC);

CREATE TABLE IF NOT EXISTS readiness (
    id SERIAL PRIMARY KEY,
    ward_id INTEGER REFERENCES wards(ward_id) UNIQUE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    drainage_score FLOAT CHECK (drainage_score BETWEEN 0 AND 100),
    pump_score FLOAT CHECK (pump_score BETWEEN 0 AND 100),
    desilting_score FLOAT CHECK (desilting_score BETWEEN 0 AND 100),
    incident_score FLOAT CHECK (incident_score BETWEEN 0 AND 100),
    composite_score FLOAT GENERATED ALWAYS AS
        ((drainage_score + pump_score + desilting_score + incident_score) / 4.0) STORED,
    updated_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS alert_log (
    id BIGSERIAL PRIMARY KEY,
    ward_id INTEGER REFERENCES wards(ward_id),
    dispatched_at TIMESTAMPTZ DEFAULT NOW(),
    alert_tier VARCHAR(20) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    delivery_status VARCHAR(20),
    message_id VARCHAR(100),
    retry_count INTEGER DEFAULT 0,
    CONSTRAINT alert_log_tier_check
        CHECK (alert_tier IN ('YELLOW', 'RED', 'ALL_CLEAR')),
    CONSTRAINT alert_log_channel_check
        CHECK (channel IN ('SMS', 'WHATSAPP')),
    CONSTRAINT alert_log_delivery_status_check
        CHECK (delivery_status IN ('SENT', 'FAILED', 'PENDING') OR delivery_status IS NULL)
);

CREATE INDEX IF NOT EXISTS alert_log_ward_dispatched_at_idx
    ON alert_log (ward_id, dispatched_at DESC);
CREATE INDEX IF NOT EXISTS alert_log_ward_tier_dispatched_at_idx
    ON alert_log (ward_id, alert_tier, dispatched_at DESC);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    flow_name VARCHAR(100) NOT NULL,
    run_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20),
    duration_seconds FLOAT,
    error_message TEXT,
    CONSTRAINT pipeline_runs_status_check
        CHECK (status IN ('RUNNING', 'COMPLETE', 'FAILED') OR status IS NULL)
);

DO $$
DECLARE
    y INT;
    m INT;
    start_date DATE;
    end_date DATE;
    partition_name TEXT;
BEGIN
    -- Ensure inserts always succeed even when pg_partman is unavailable.
    FOR y IN 2003..2035 LOOP
        FOR m IN 1..12 LOOP
            start_date := make_date(y, m, 1);
            end_date := (start_date + INTERVAL '1 month')::date;

            partition_name := format('ward_features_%s_%s', y, lpad(m::text, 2, '0'));
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF ward_features
                 FOR VALUES FROM (%L) TO (%L)',
                partition_name, start_date, end_date
            );
        END LOOP;
    END LOOP;
    EXECUTE 'CREATE TABLE IF NOT EXISTS ward_features_default PARTITION OF ward_features DEFAULT';

    FOR y IN 2024..2035 LOOP
        FOR m IN 1..12 LOOP
            start_date := make_date(y, m, 1);
            end_date := (start_date + INTERVAL '1 month')::date;

            partition_name := format('predictions_%s_%s', y, lpad(m::text, 2, '0'));
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF predictions
                 FOR VALUES FROM (%L) TO (%L)',
                partition_name, start_date, end_date
            );
        END LOOP;
    END LOOP;
    EXECUTE 'CREATE TABLE IF NOT EXISTS predictions_default PARTITION OF predictions DEFAULT';
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM partman.part_config
                WHERE parent_table = 'public.ward_features'
            ) THEN
                PERFORM partman.create_parent(
                    p_parent_table => 'public.ward_features',
                    p_control => 'computed_at',
                    p_type => 'native',
                    p_interval => 'monthly',
                    p_premake => 4
                );
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM partman.part_config
                WHERE parent_table = 'public.predictions'
            ) THEN
                PERFORM partman.create_parent(
                    p_parent_table => 'public.predictions',
                    p_control => 'predicted_at',
                    p_type => 'native',
                    p_interval => 'monthly',
                    p_premake => 4
                );
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'pg_partman parent setup skipped due to: %', SQLERRM;
        END;

        UPDATE partman.part_config
        SET premake = 4,
            infinite_time_partitions = TRUE,
            retention = '90 days',
            retention_keep_table = TRUE,
            retention_keep_index = TRUE,
            retention_schema = 'archive'
        WHERE parent_table IN ('public.ward_features', 'public.predictions');

        BEGIN
            PERFORM partman.run_maintenance();
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'pg_partman maintenance skipped due to: %', SQLERRM;
        END;
    ELSE
        RAISE NOTICE 'Skipping pg_partman parent/retention setup because extension is unavailable.';
    END IF;
END
$$;
