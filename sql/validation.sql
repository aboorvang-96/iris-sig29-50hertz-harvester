\pset pager off
\echo '== 1. count by geom_status =='
SELECT geom_status, count(*) AS records
FROM iris_staging.signal_ingest
GROUP BY geom_status
ORDER BY geom_status;

\echo '== 2. records with NULL capacity =='
SELECT source_id, capacity_mw
FROM iris_staging.signal_ingest
WHERE capacity_mw IS NULL
ORDER BY source_id;

\echo '== 3. duplicate check on (source, source_id) =='
SELECT source, source_id, count(*) AS records
FROM iris_staging.signal_ingest
GROUP BY source, source_id
HAVING count(*) > 1
ORDER BY source, source_id;

\echo '== 4. SRID and geometry type =='
SELECT source_id, ST_SRID(geom) AS srid, ST_GeometryType(geom) AS geom_type
FROM iris_staging.signal_ingest
ORDER BY source_id;

\echo '== 5. null geometry count and total =='
SELECT count(*) FILTER (WHERE geom IS NULL) AS null_geom, count(*) AS total
FROM iris_staging.signal_ingest;

\echo '== 6. capacity basis / generation / deadlines =='
SELECT source_id,
       capacity_mw,
       attributes->>'capacity_basis' AS capacity_basis,
       attributes->>'generation_capacity_mw' AS generation_mw,
       attributes->'completion_deadlines' AS completion_deadlines
FROM iris_staging.signal_ingest
ORDER BY source_id;

\echo '== 7. stored row summary =='
SELECT source_id, title, published_at, geom_status,
       round(ST_X(geom)::numeric, 2) AS x_25832,
       round(ST_Y(geom)::numeric, 2) AS y_25832
FROM iris_staging.signal_ingest
ORDER BY source_id;
