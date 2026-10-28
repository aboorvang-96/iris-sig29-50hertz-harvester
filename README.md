# IRIS-SIG-29 — 50Hertz Transmission Grid Expansion Alerts Harvester

A Python CLI that extracts public 50Hertz offshore grid-connection project
information, normalizes it, resolves onshore locations to EPSG:25832 points where
possible, and loads it idempotently into `iris_staging.signal_ingest`.

- **Task:** IRIS-SIG-29, 50Hertz Transmission Grid Expansion Alerts Harvester
- **Integration pattern:** B (HTML)
- **Destination:** `iris_staging.signal_ingest` (PostgreSQL 16 / PostGIS 3.4)
- **Runtime:** Python 3.11
- **Default mode:** offline fixture run; live fetch is available with `--live`

The implementation is a batch CLI, not a scheduler or a production crawl service.
It is deliberately conservative: it refuses to crawl when robots.txt is
unavailable, fails loudly when a page layout changes, and never invents a
publication date or a coordinate.

---

## Task

Ingest East/North substation connections and offshore wind landing capacities for
the 50Hertz transmission grid.

The harvester:

1. reads four 50Hertz English offshore grid-connection project pages;
2. extracts project identity, capacity, onshore/offshore location context,
   completion deadlines and source facts;
3. resolves the onshore connection point through a local gazetteer and projects
   it from WGS84 to EPSG:25832;
4. writes a JSONL artifact and, when a DSN is configured, upserts records into
   `iris_staging.signal_ingest`;
5. reports inserted, updated, unchanged and per-source errors.

It does **not** ingest a news/alert feed: the alternative pages are static
project pages. See [Known limitations](#known-limitations).

---

## Source and access verification

### Brief endpoint

The brief endpoint `https://www.50hertz.com/de/Netzanschluss` redirected to
`wartung.50hertz.com/Error` with the message **“The requested site can
unfortunately not be displayed”** when checked manually in a browser at
**18:22 IST on 28 October 2026**. It is therefore treated as obsolete or
unavailable. No attempt is made to bypass that restriction.

### Justified alternative

The English offshore grid-connection project pages under
`https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/` are used:

| Project | Source page |
|---|---|
| OST-6-1 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/GridconnectionOST-6-1 |
| Ostwind 2 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind2 |
| Ostwind 3 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind3 |
| Ostwind 4 | https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind4 |

These pages match the brief’s objective: they publish offshore wind landing
capacity, onshore connection points (Gnewitz, Lubmin, Stilow) and the associated
grid-connection projects.

### Access rules and fixtures

- `robots.txt` was checked and saved in `tests/fixtures/robots.txt`. The wildcard
  rules do not disallow these paths. The harvester honours robots.txt and
  enforces a delay between requests. If robots.txt cannot be fetched, the live
  run fails closed.
- Fixtures were saved manually in a browser on **28 October 2026**; see
  `tests/fixtures/MANIFEST.md` for URLs, byte sizes and SHA-256 hashes. Tests run
  fully offline.
- The pages show no publication date, so `published_at` is `NULL`. Completion
  deadlines are stored in `attributes.completion_deadlines` only.
- A live run was also executed once with `--live --request-delay 2`; it produced
  the same four content hashes as the offline run. Automated tests remain offline.

---

## Data model and mapping assumptions

### Table

`sql/001_schema.sql` creates `iris_staging.signal_ingest`:

| Column | Type | Meaning |
|---|---|---|
| `id` | `bigserial` | surrogate key |
| `source` | `text` | always `50hertz` |
| `source_id` | `text` | stable project id derived from the page `<h1>` (`OST-6-1`, `ostwind-2`, …) |
| `signal_type` | `text` | `offshore_grid_connection` |
| `title` | `text` | project heading |
| `url` | `text` | canonical project URL (taken from the page form action) |
| `published_at` | `timestamptz` | `NULL`; the source pages publish no date |
| `capacity_mw` | `numeric(12,2)` | see capacity rule below |
| `location_text` | `text` | derived onshore + offshore description |
| `geom` | `geometry(Point,25832)` | onshore point when the gazetteer resolves it |
| `geom_status` | `text` | `resolved`, `approximate`, `unresolved` or `invalid` |
| `content_hash` | `text` | SHA-256 of the normalized record |
| `attributes` | `jsonb` | source facts and extraction diagnostics |
| `first_seen_at` | `timestamptz` | first insert time |
| `last_seen_at` | `timestamptz` | last time the record was seen |
| `updated_at` | `timestamptz` | last time content changed |

`UNIQUE (source, source_id)` is the duplicate guard.

### Identity and change detection

- `source_id` is derived deterministically from the heading: `OST-6-1` keeps its
  code; `Ostwind 2` becomes `ostwind-2`. It is not a random UUID, so re-runs
  address the same row.
- `content_hash` is SHA-256 over canonical JSON containing the mapped fields and
  attributes. Timestamps and database ids are excluded, so an unchanged page
  produces the same hash.
- `first_seen_at` is set on insert; `last_seen_at` is refreshed on every run;
  `updated_at` changes only when `content_hash` changes.

### Capacity

`capacity_mw` is the **transmission capacity** when the page states one, with any
separately stated generation figure kept in
`attributes.generation_capacity_mw`:

| Project | `capacity_mw` | `capacity_basis` | Generation figure |
|---|---:|---|---:|
| OST-6-1 | 927 | `generation` | 927 MW |
| Ostwind 2 | 750 | `transmission` | 725 MW |
| Ostwind 3 | 300 | `generation` | 300 MW |
| Ostwind 4 | 2000 | `transmission` | 1000 MW |

For OST-6-1 and Ostwind 3 the page publishes only one project capacity figure, so
that figure is used and labelled `generation`. For Ostwind 2 the page has no
capacity row; 750 MW is extracted from the prose “can transmit a total of 750 MW”.
For Ostwind 4 the table states “Total transmission capacity: 2,000 megawatts”,
while the wind farm target is 1 GW. No capacity is fabricated when absent: the
field stays `NULL` and `attributes.missing_fields` records it.

### Location text

`location_text` joins the extracted onshore connection point and the offshore
location description, for example:

```text
Lubmin substation (onshore connection point); offshore: approx. 20 km / 30 km to north-east of Rügen
```

`attributes.onshore_connection_point`, `attributes.offshore_location` and
`attributes.geocode_name` preserve the individual source values. Offshore wind
farm areas are areas, not point features, and are not converted into points.

### Attributes

`attributes` (jsonb) includes only source-derived or extraction-diagnostic values:

- `project_name`, `page_title`
- `onshore_connection_point`, `offshore_location`, `offshore_location_label`,
  `geocode_name`
- `capacity_basis`, `capacity_source`, `capacity_source_text`,
  `generation_capacity_mw`
- `voltage_level`, `voltage_source_text`, `route_length`, `operator`,
  `approval_status`
- `completion_deadlines` (ISO dates; Ostwind 2 keeps its three designated
  milestones)
- `publication_date` (`null`) and `publication_date_note`
- `missing_fields`

---

## Geometry

- **Gazetteer approach:** `tests/fixtures/gazetteer.csv` contains `name`, `lat`,
  `lon`, `precision` and `source`. Matching is exact (case-insensitive,
  whitespace-normalized); there is no fuzzy matching.
- **Projection:** WGS84 (EPSG:4326) to **EPSG:25832** with `pyproj`, using
  `always_xy=True`.
- **Bounding-box validation:** latitude must be within **47..56** and longitude
  within **5..16**. Coordinates outside the box are rejected.
- **Statuses:**
  - `resolved` — exact gazetteer match with valid projected coordinates;
  - `approximate` — valid match, but the gazetteer entry is a village centre;
  - `unresolved` — no gazetteer entry / no onshore place name; `geom` is `NULL`;
  - `invalid` — non-numeric, outside the bounding box, or projection failure;
    `geom` is `NULL` and the reason is retained.
- **Lubmin** is the **village centre (approximate)** because the Lubmin
  substation was not found by name in OpenStreetMap. Gnewitz and Stilow are
  likewise village centres marked approximate; the exact substations were not
  resolved by name in OpenStreetMap.
- All four current records therefore carry `geom_status = 'approximate'`, not
  survey-grade substation coordinates.

### CRS note

EPSG:25832 is **UTM zone 32N**. Sites east of about **12° E** (for example near
Rügen) lie in **zone 33**, so projecting them into 25832 still works but
introduces some distortion. The brief mandates 25832, so that CRS is retained
and the distortion is documented rather than silently changing the CRS.

---

## Setup and run (Windows PowerShell)

Prerequisites: Python 3.11, Docker Desktop (for the compose file), and network
access only for `--live` and image pulls. The test suite needs no network.

```powershell
# 1. Environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 2. Configuration (no credentials in source)
Copy-Item .env.example .env
notepad .env   # set POSTGRES_PASSWORD and IRIS_DATABASE_URL

# 3. PostGIS 3.4 (PostgreSQL 16)
docker compose up -d
docker compose ps

# 4. Schema
Get-Content .\sql\001_schema.sql -Raw |
    docker compose exec -T postgis psql -U iris -d iris

# 5. Offline CLI run (no database)
python -m iris_harvester --offline --no-db

# 6. Offline CLI run with database load
python -m iris_harvester --offline

# 7. Live run (robots.txt enforced, 2 s between requests)
python -m iris_harvester --live --request-delay 2

# 8. Tests
python -m pytest
```

The JSONL artifact is written to `out/signals.jsonl` by default; use
`--output <path>` to change it. `--fixtures-dir` and `--gazetteer` override the
default fixture paths. If `IRIS_DATABASE_URL` is unset, the CLI still writes the
artifact and reports `database=skipped`; use `--no-db` to skip the load even when
a DSN is present. The four-record artifact from the recorded run is committed at
`docs/sample_signals.jsonl`.

### Applying the schema with `psql` directly

If `psql` is installed on Windows:

```powershell
psql $env:IRIS_DATABASE_URL -f .\sql\001_schema.sql
psql $env:IRIS_DATABASE_URL -f .\sql\validation.sql
```

---

## Idempotency and re-run behaviour

For each record the loader:

1. reads the existing `content_hash` for `(source, source_id)`;
2. **inserts** when no row exists;
3. **updates** the mutable columns and `updated_at` when the hash differs;
4. **touches only `last_seen_at`** when the hash is unchanged.

The unique constraint on `(source, source_id)` is the final guard. Counters are
printed by the CLI and are also returned by `load_records()`.

Real consecutive runs against a fresh PostGIS database:

```text
first run:  database=loaded inserted=4 updated=0 unchanged=0
second run: database=loaded inserted=0 updated=0 unchanged=4
```

A second identical offline run also produces a byte-identical JSONL artifact.
If a source page changes, the same row is updated (`updated=1`) rather than
duplicated. A duplicate `source_id` inside one run is reported as an error and
the second record is not added.

---

## Error handling

| Error | When |
|---|---|
| `SourceUnavailableError` | HTTP failure, empty body, unusable live payload, missing fixture |
| `RobotsDeniedError` | robots.txt disallows the URL, or robots.txt is unavailable (fail closed) |
| `ParseError` | empty/malformed HTML, no heading, no data table, no recognizable fields |
| `ConfigurationError` | missing/invalid gazetteer (bad coordinates, duplicate names) |
| `DatabaseLoadError` | PostgreSQL load/transaction failure |

- **Retries:** live requests make up to 3 attempts. Retryable conditions are
  network exceptions and HTTP 429/500/502/503/504; backoff is 1 s then 2 s.
  Other 4xx responses fail immediately.
- **Throttling:** a delay (default 2 s, configurable) is enforced between live
  requests; the effective delay is the larger of the configured delay and any
  applicable robots `Crawl-delay`.
- **Empty/malformed pages:** the page is reported as an error; no empty record is
  emitted.
- **Missing fields:** optional fields are `NULL` and listed in
  `attributes.missing_fields`; nothing is invented.
- **Invalid coordinates:** `geom_status='invalid'`, `geom=NULL`, and a reason is
  retained in the artifact. Invalid coordinates are never silently accepted.
- **Exit codes:** `0` success, `1` configuration/database failure, `2` one or
  more per-source fetch/parse errors (records that did parse are still written).

---

## Tests

The suite is fully offline and uses the four saved pages plus the saved
robots.txt. Final local result: **51 passed**.

| File | Coverage |
|---|---|
| `tests/test_parser.py` | all four fixture pages; exact titles, ids, capacities, capacity basis, generation figures, completion dates; NULL publication dates; URL extraction; empty/malformed pages; missing capacity visible; unknown layout fails |
| `tests/test_geocoding.py` | all three onshore points; Lubmin coordinate/projection; unresolved names; out-of-bbox invalid; non-numeric and duplicate gazetteer entries; exact vs approximate status |
| `tests/test_robots.py` | saved robots.txt allows project paths, blocks `/admin/` and `/images/`; `Crawl-delay` parsing |
| `tests/test_client.py` | 5xx and network retry, exhausted retries, 404 not retried, robots denial, empty body, fail-closed robots, request delay |
| `tests/test_storage.py` | insert → unchanged → update counters; separate source ids; 25832 geometry SQL; NULL geometry |
| `tests/test_harvester.py` | all four records, missing fixture, malformed fixture, duplicate `source_id`, live mode requires a client, live payload path, stable hashes |
| `tests/test_cli.py` | offline JSONL output, field values, byte-identical re-run, error exit code, invalid gazetteer exit code |
| `tests/conftest.py` | shared parser, geocoder and fixture paths |

What is **not** covered automatically: a real PostGIS load inside pytest (the
loader is tested with a fake connection), the live site, and browser rendering.
The real PostGIS load and validation queries were run manually; see
`docs/QUALITY_REPORT.md`.

---

## Known limitations

- **The brief endpoint is unavailable.** The alternative pages are static project
  pages, not a dedicated alert feed. They do not expose an alert severity, an
  event timestamp or a publication date. The output is therefore a normalized
  project snapshot, not a stream of dated alerts.
- **Only four pages are configured.** There is no index crawl and no pagination;
  the alternative site exposes the projects as separate pages. Adding a project
  requires a `ProjectSource` entry and, for offline tests, a new fixture.
- **No publication date exists on the pages.** `published_at` is always `NULL`;
  completion deadlines are kept in attributes only.
- **HTML structure may change.** The parser depends on `<h1>`, `<main>`, tables
  and form actions from the saved DNN pages. It fails loudly rather than emitting
  an empty record, but a redesign will require parser maintenance.
- **The gazetteer is very small (3 entries).** Only Lubmin, Gnewitz and Stilow are
  present, all as approximate village centres. The exact substations were not
  resolved by name in OpenStreetMap, and there is no external geocoding service
  or fuzzy matching. Offshore wind-farm areas are kept as text, not points.
- **Projection distortion.** Sites east of about 12° E are in UTM zone 33 but are
  projected into zone 32N (EPSG:25832) as required; this introduces some
  distortion. Coordinates are approximate and are not survey-grade.
- **Capacity semantics vary.** OST-6-1 and Ostwind 3 have no separately published
  transmission rating, so `capacity_mw` is their generation/project capacity.
  The basis is explicit in `attributes.capacity_basis`; consumers must not treat
  every `capacity_mw` as a transmission rating.
- **Live mode is implemented but not in the automated suite.** It was run
  manually against the live site and produced the same hashes as the fixtures.
  There is no scheduled execution, no incremental checkpoint and no
  monitoring/alerting.
- **Database integration is not in pytest.** The SQL was applied and the loader
  was exercised against a real PostGIS instance manually; pytest uses a fake
  connection. There is no CI pipeline in this repository.
- **robots.txt can change.** The saved copy is evidence for the capture date; the
  live path fetches and honours the current robots.txt at runtime.
- **No credentials are stored in source.** Configuration is via `.env` /
  environment variables; `.env` is git-ignored.

---

## Repository layout

```text
src/iris_harvester/      package (CLI, parser, geocoder, robots, client, storage)
sql/001_schema.sql       schema, constraints and indexes
sql/validation.sql       operational validation queries
tests/                   offline pytest suite
tests/fixtures/          manually saved HTML, robots.txt, gazetteer, MANIFEST
docs/QUALITY_REPORT.md   real run, extraction and validation evidence
docs/sample_signals.jsonl  four-record JSONL artifact from the recorded run
out/                     local run output (git-ignored)
```

---

## AI assistance disclosure

This solution was planned with **Claude (claude.ai)** and implemented with
**OpenCode using DeepSeek**. The original endpoint was first checked once by an AI
assistant tool and then confirmed manually in a browser. The author reviewed the
code and ran the tests.
