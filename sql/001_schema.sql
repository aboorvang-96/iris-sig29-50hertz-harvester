-- IRIS-SIG-29 destination schema.
-- Target: PostgreSQL 16 with PostGIS 3.4 (docker-compose.yml pins 3.4-16).
-- Apply with: psql "$env:IRIS_DATABASE_URL" -f sql/001_schema.sql

CREATE SCHEMA IF NOT EXISTS iris_staging;

CREATE TABLE IF NOT EXISTS iris_staging.signal_ingest (
    id              bigserial PRIMARY KEY,
    source          text        NOT NULL,
    source_id       text        NOT NULL,
    signal_type     text        NOT NULL,
    title           text        NOT NULL,
    url             text        NOT NULL,
    published_at    timestamptz,
    capacity_mw     numeric(12, 2),
    location_text   text,
    geom            geometry(Point, 25832),
    geom_status     text        NOT NULL,
    content_hash    text        NOT NULL,
    attributes      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT signal_ingest_source_id_key UNIQUE (source, source_id),
    CONSTRAINT signal_ingest_geom_status_check
        CHECK (geom_status IN ('resolved', 'approximate', 'unresolved', 'invalid')),
    CONSTRAINT signal_ingest_capacity_check
        CHECK (capacity_mw IS NULL OR capacity_mw >= 0)
);

CREATE INDEX IF NOT EXISTS signal_ingest_geom_gix
    ON iris_staging.signal_ingest USING gist (geom);

CREATE INDEX IF NOT EXISTS signal_ingest_source_idx
    ON iris_staging.signal_ingest (source);

CREATE INDEX IF NOT EXISTS signal_ingest_published_at_idx
    ON iris_staging.signal_ingest (published_at);

COMMENT ON TABLE iris_staging.signal_ingest IS
    'Normalized public-source signals for IRIS. One row per (source, source_id).';
COMMENT ON COLUMN iris_staging.signal_ingest.source_id IS
    'Stable project identifier derived from the page heading (e.g. OST-6-1, ostwind-2).';
COMMENT ON COLUMN iris_staging.signal_ingest.capacity_mw IS
    'Transmission capacity when published; otherwise the only published project capacity. See attributes.capacity_basis.';
COMMENT ON COLUMN iris_staging.signal_ingest.geom IS
    'Point in EPSG:25832, populated only for exact/approximate gazetteer matches.';
COMMENT ON COLUMN iris_staging.signal_ingest.geom_status IS
    'resolved | approximate | unresolved | invalid.';
COMMENT ON COLUMN iris_staging.signal_ingest.content_hash IS
    'SHA-256 over the normalized content; unchanged hashes are not rewritten.';
