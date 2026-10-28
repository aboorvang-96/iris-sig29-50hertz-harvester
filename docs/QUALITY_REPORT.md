# Quality report — IRIS-SIG-29

**Run date:** 28 October 2026
**Application environment:** Windows, Python 3.11.9, pytest 8.4.2
**Database validation environment:** PostgreSQL 16.15 with PostGIS 3.6.4 (WSL
Ubuntu 22.04). `docker-compose.yml` pins `postgis/postgis:3.4-16`; that exact
image was not available in this environment, so the SQL was validated on 3.6.4.
The schema uses only stable PostGIS features (`geometry(Point,25832)`,
`ST_SetSRID`, `ST_MakePoint`, `ST_SRID`).

---

## a) pytest result

Command:

```text
python -m pytest -q
```

Result:

```text
...................................................                      [100%]
51 passed in 2.31s
```

No failures, errors or skips. The suite is fully offline and uses the four
fixtures plus the saved `robots.txt`. (The reported duration varies slightly
between runs; the pass/fail result does not.)

---

## b) CLI run summary

### Offline, first run against an empty table

```text
IRIS-SIG-29 50Hertz harvester
mode=offline sources=4
parsed=4 errors=0 capacity_present=4 capacity_missing=0
geometry=resolved:0 approximate:4 unresolved:0 invalid:0
output=out\signals.jsonl records=4
database=loaded inserted=4 updated=0 unchanged=0
```

### Offline, immediate re-run

```text
IRIS-SIG-29 50Hertz harvester
mode=offline sources=4
parsed=4 errors=0 capacity_present=4 capacity_missing=0
geometry=resolved:0 approximate:4 unresolved:0 invalid:0
output=out\signals.jsonl records=4
database=loaded inserted=0 updated=0 unchanged=4
```

The JSONL artifact contained four lines on both runs and was byte-identical.
The full four-line sample from the recorded run is committed at
`docs/sample_signals.jsonl`.

### Live run (supplementary verification)

```text
IRIS-SIG-29 50Hertz harvester
mode=live sources=4
parsed=4 errors=0 capacity_present=4 capacity_missing=0
geometry=resolved:0 approximate:4 unresolved:0 invalid:0
output=out\signals_live.jsonl records=4
database=skipped (--no-db)
```

The live run used `--request-delay 2` and the current robots.txt. Its four
`content_hash` values were equal to the offline artifact’s hashes. Live fetching
is not part of the automated pytest suite.

Sample normalized record (OST-6-1, artifact values, subset):

```json
{
  "source_id": "OST-6-1",
  "published_at": null,
  "capacity_mw": 927.0,
  "location_text": "Gnewitz substation (onshore connection point); offshore: Around 15 km north of the Fischland-Darß-Zingst peninsula or 24 km west of the island of Hiddensee",
  "geom_status": "approximate",
  "attributes": {
    "capacity_basis": "generation",
    "generation_capacity_mw": 927.0,
    "completion_deadlines": [{"date": "2028-07-01"}],
    "missing_fields": ["published_at"]
  }
}
```

---

## c) Extracted and missing fields per fixture page

### OST-6-1.html

| Field | Extracted? | Value |
|---|---|---|
| Title / URL | yes | `Grid connection OST-6-1` / `https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/GridconnectionOST-6-1` |
| `published_at` | **missing** | `NULL` (page has no publication date) |
| `capacity_mw` | yes | `927.0` |
| `capacity_basis` / generation | yes | `generation` / `927.0` MW |
| Onshore connection point | yes | `Gnewitz substation` |
| Offshore location | yes | `Around 15 km north of the Fischland-Darß-Zingst peninsula or 24 km west of the island of Hiddensee` |
| Voltage / route | yes | `220 kV` / `Around 35 to 53 km / around 35 km` |
| Completion deadline | yes | `2028-07-01` |
| Geometry | yes, approximate | Gnewitz village centre, `54.0788474, 12.5132459` → `729811.41, 5998003.18` (EPSG:25832) |
| `missing_fields` | — | `["published_at"]` |

### Ostwind 2.html

| Field | Extracted? | Value |
|---|---|---|
| Title / URL | yes | `Ostwind 2` / `https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind2` |
| `published_at` | **missing** | `NULL` (page has no publication date) |
| `capacity_mw` | yes | `750.0` (transmission, from prose; the page has no capacity row) |
| `capacity_basis` / generation | yes | `transmission` / `725.0` MW |
| Onshore connection point | yes | `Lubmin substation` |
| Offshore location | yes | `approx. 20 km / 30 km to north-east of Rügen` |
| Voltage / route | yes | `220 kV` (prose fallback) / `approx. 90 km` |
| Completion deadlines | yes | `OST-2-1 2023-09-30`, `OST-2-2 2023-12-31`, `OST-2-3 2024-09-30` |
| Geometry | yes, approximate | Lubmin village centre, `54.14481, 13.64847` → `803541.98, 6009622.72` (EPSG:25832) |
| `missing_fields` | — | `["published_at"]` |

### Ostwind 3.html

| Field | Extracted? | Value |
|---|---|---|
| Title / URL | yes | `Ostwind 3` / `https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind3` |
| `published_at` | **missing** | `NULL` (page has no publication date) |
| `capacity_mw` | yes | `300.0` |
| `capacity_basis` / generation | yes | `generation` / `300.0` MW |
| Onshore connection point | yes | `Near Stilow` |
| Offshore location | yes | `Approximately 42 kilometres north-east of Rügen` |
| Voltage / route | yes | `220 kilovolts (kV)` / `Approximately 100 kilometres / approximately four and a half kilometres` |
| Completion deadline | yes | `2026-09-30` |
| Geometry | yes, approximate | Stilow village centre, `54.0887941, 13.5721214` → `798963.24, 6003070.85` (EPSG:25832) |
| `missing_fields` | — | `["published_at"]` |

### Ostwind 4.html

| Field | Extracted? | Value |
|---|---|---|
| Title / URL | yes | `Ostwind 4` / `https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind4` |
| `published_at` | **missing** | `NULL` (page has no publication date) |
| `capacity_mw` | yes | `2000.0` (total transmission capacity) |
| `capacity_basis` / generation | yes | `transmission` / `1000.0` MW |
| Onshore connection point | yes | `Substation with converter at Stilow` |
| Offshore location | yes | `Approximately 40 kilometres north-east of Rügen` |
| Voltage / route | yes | `525 kilovolts of direct voltage` / `Approximately 110 kilometres / 4 kilometres` |
| Completion deadline | yes | `2031-05-31` |
| Geometry | yes, approximate | Stilow village centre, `54.0887941, 13.5721214` → `798963.24, 6003070.85` (EPSG:25832) |
| `missing_fields` | — | `["published_at"]` |

---

## d) Unresolved locations and why

No stored record has `geom_status='unresolved'`: all four onshore connection
points matched the gazetteer and were projected. The unresolved geographic
context is offshore, and it is intentionally kept as text:

| Offshore area | Project | Why no point geometry |
|---|---|---|
| Gennaker / O-6 area, around 15 km north of Fischland-Darß-Zingst | OST-6-1 | the page describes an offshore wind-farm area and distance, not a point; the gazetteer has no offshore entry |
| Clusters Westlich Arkonasee / Arkonasee | Ostwind 2 | area in the EEZ/12-mile zone; only distance-to-coast descriptions are published |
| Westlich Adlergrund area / Windanker | Ostwind 3 | area description, no coordinate published |
| O-2.2 area / OstSee Energies | Ostwind 4 | area description, no coordinate published |

Onshore, Lubmin, Gnewitz and Stilow are **village centres marked approximate**.
The exact substations were not found by name in OpenStreetMap, so no
`geom_status='resolved'` rows exist. A future gazetteer miss would produce
`unresolved` with a reason in the artifact rather than a guessed coordinate.

---

## e) Validation SQL queries and real outputs

These are the queries in `sql/validation.sql`, run with `psql` against the loaded
database.

### Count by `geom_status`

```sql
SELECT geom_status, count(*) AS records
FROM iris_staging.signal_ingest
GROUP BY geom_status
ORDER BY geom_status;
```

```text
 geom_status | records
-------------+---------
 approximate |       4
(1 row)
```

### Records with NULL capacity

```sql
SELECT source_id, capacity_mw
FROM iris_staging.signal_ingest
WHERE capacity_mw IS NULL
ORDER BY source_id;
```

```text
 source_id | capacity_mw
-----------+-------------
(0 rows)
```

### Duplicate check on `(source, source_id)` — zero rows

```sql
SELECT source, source_id, count(*) AS records
FROM iris_staging.signal_ingest
GROUP BY source, source_id
HAVING count(*) > 1
ORDER BY source, source_id;
```

```text
 source | source_id | records
--------+-----------+---------
(0 rows)
```

### SRID check using `ST_SRID`

```sql
SELECT source_id, ST_SRID(geom) AS srid, ST_GeometryType(geom) AS geom_type
FROM iris_staging.signal_ingest
ORDER BY source_id;
```

```text
 source_id | srid  | geom_type
-----------+-------+-----------
 OST-6-1   | 25832 | ST_Point
 ostwind-2 | 25832 | ST_Point
 ostwind-3 | 25832 | ST_Point
 ostwind-4 | 25832 | ST_Point
(4 rows)
```

### NULL geometry check

```sql
SELECT count(*) FILTER (WHERE geom IS NULL) AS null_geom, count(*) AS total
FROM iris_staging.signal_ingest;
```

```text
 null_geom | total
-----------+-------
         0 |     4
(1 row)
```

---

## f) Known data-quality issues

1. **No publication dates.** Every page lacks one, so `published_at` is `NULL`
   for all four records. The data cannot be ordered or filtered by publication
   time, and there is no incremental “since” retrieval.
2. **Geometry is approximate.** All four points are village centres, not
   substations. The exact onshore substations were not resolved by name in
   OpenStreetMap. Horizontal accuracy is therefore village-centre level, not
   asset-level, and the report does not claim a metre figure.
3. **CRS distortion.** EPSG:25832 is UTM zone 32N, while the Rügen-area sites are
   east of about 12° E in zone 33. The required 25832 projection is used, so
   some distortion is inherent.
4. **Mixed capacity semantics.** `capacity_mw` is 750/2000 MW transmission
   capacity for Ostwind 2/4, but 927/300 MW generation/project capacity for
   OST-6-1/Ostwind 3 because no separate transmission rating is published.
   `attributes.capacity_basis` must be read with the value.
5. **Prose-derived values.** Ostwind 2 has no capacity row; 750 MW and 220 kV are
   extracted from prose. A copy edit on the page could break these fallbacks.
6. **Completion dates are deadlines, not publication/event dates.** Ostwind 2’s
   three milestones (2023-09-30, 2023-12-31, 2024-09-30) are already in the past
   at capture time; the page also states the connections were commissioned.
   OST-6-1 (2028-07-01), Ostwind 3 (2026-09-30) and Ostwind 4 (2031-05-31) are
   future deadlines.
7. **Static project pages, not an alert feed.** There is no alert severity,
   event timestamp or per-alert identifier. The four records are a project
   snapshot.
8. **Source drift.** The live pages matched the fixtures on 28 October 2026, but
   page HTML and project facts can change. The parser fails loudly on a changed
   layout; it does not silently emit empty rows.
9. **Small, manual gazetteer.** Three entries, exact-name matching, no fuzzy
   matching and no external geocoder. A new onshore place will be `unresolved`
   until the CSV is extended.
10. **Naming convention is mixed.** The project code is retained for OST-6-1
    while Ostwind pages use slugs (`ostwind-2`, etc.). The ids are stable, but not
    uniform in style.
11. **Environment difference.** Database validation used PostgreSQL 16.15 /
    PostGIS 3.6.4; the compose file targets PostGIS 3.4 on PostgreSQL 16. The SQL
    is standard, but the exact 3.4 image was not exercised here.
12. **No automated database or live-site test.** Pytest uses a fake connection
    for the loader; the actual PostGIS load and live fetch were run manually. No
    CI pipeline is included.
