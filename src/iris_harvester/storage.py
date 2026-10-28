"""Idempotent PostgreSQL/PostGIS loading."""

from __future__ import annotations

from typing import Any, Protocol

from psycopg.types.json import Jsonb

from .errors import DatabaseLoadError
from .models import LoadResult, SignalRecord

TABLE = "iris_staging.signal_ingest"

_SELECT_HASH = (
    f"SELECT content_hash FROM {TABLE} WHERE source = %s AND source_id = %s"
)

_INSERT = f"""
INSERT INTO {TABLE}
    (source, source_id, signal_type, title, url, published_at, capacity_mw,
     location_text, geom, geom_status, content_hash, attributes)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, {{geom}}, %s, %s, %s)
RETURNING id
"""

_UPDATE = f"""
UPDATE {TABLE}
SET title = %s,
    url = %s,
    published_at = %s,
    capacity_mw = %s,
    location_text = %s,
    geom = {{geom}},
    geom_status = %s,
    content_hash = %s,
    attributes = %s,
    last_seen_at = now(),
    updated_at = now()
WHERE source = %s AND source_id = %s
"""

_TOUCH = f"""
UPDATE {TABLE}
SET last_seen_at = now()
WHERE source = %s AND source_id = %s
"""


class ConnectionLike(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ...) -> Any: ...
    def transaction(self) -> Any: ...


def load_records(connection: ConnectionLike, records: list[SignalRecord]) -> LoadResult:
    """Insert new rows, update changed rows, touch unchanged rows.

    The pre-read of ``content_hash`` makes the counters explicit. The unique
    constraint on ``(source, source_id)`` remains the final duplicate guard.
    """

    result = LoadResult()
    try:
        with connection.transaction():
            for record in records:
                row = connection.execute(
                    _SELECT_HASH,
                    (record.source, record.source_id),
                ).fetchone()

                if row is None:
                    geom_sql, geom_params = _geom(record)
                    connection.execute(
                        _INSERT.format(geom=geom_sql),
                        (
                            record.source,
                            record.source_id,
                            record.signal_type,
                            record.title,
                            record.url,
                            record.published_at,
                            record.capacity_mw,
                            record.location_text,
                            *geom_params,
                            record.geom_status,
                            record.content_hash,
                            Jsonb(record.attributes),
                        ),
                    )
                    result.inserted += 1
                    continue

                existing_hash = row[0] if not isinstance(row, dict) else row["content_hash"]
                if existing_hash == record.content_hash:
                    connection.execute(
                        _TOUCH,
                        (record.source, record.source_id),
                    )
                    result.unchanged += 1
                    continue

                geom_sql, geom_params = _geom(record)
                connection.execute(
                    _UPDATE.format(geom=geom_sql),
                    (
                        record.title,
                        record.url,
                        record.published_at,
                        record.capacity_mw,
                        record.location_text,
                        *geom_params,
                        record.geom_status,
                        record.content_hash,
                        Jsonb(record.attributes),
                        record.source,
                        record.source_id,
                    ),
                )
                result.updated += 1
    except Exception as exc:
        raise DatabaseLoadError(f"database load failed: {exc}") from exc

    return result


def _geom(record: SignalRecord) -> tuple[str, tuple[float, float] | tuple[()]]:
    if record.geometry and record.geometry.has_geometry:
        return (
            "ST_SetSRID(ST_MakePoint(%s, %s), 25832)",
            (record.geometry.x_25832, record.geometry.y_25832),
        )
    return "NULL", ()
