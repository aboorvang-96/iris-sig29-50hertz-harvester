"""Idempotent load tests using an in-memory fake connection."""

from __future__ import annotations

from contextlib import contextmanager

from iris_harvester.models import GeoResult, SignalRecord
from iris_harvester.storage import load_records


class FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self):
        self.hashes: dict[tuple[str, str], str] = {}
        self.queries: list[tuple[str, tuple]] = []
        self.touched = 0

    def execute(self, query: str, params: tuple = ()):
        self.queries.append((query, params))
        if query.lstrip().startswith("SELECT content_hash"):
            value = self.hashes.get((params[0], params[1]))
            return FakeCursor((value,) if value else None)
        if "INSERT INTO" in query:
            self.hashes[(params[0], params[1])] = params[-2]
            return FakeCursor((1,))
        if "UPDATE" in query:
            if "updated_at" not in query:
                self.touched += 1
            else:
                self.hashes[(params[-2], params[-1])] = params[-4]
            return FakeCursor(None)
        raise AssertionError(f"unexpected query: {query}")

    @contextmanager
    def transaction(self):
        yield self


def make_record(source_id: str = "OST-6-1", title: str = "Title") -> SignalRecord:
    return SignalRecord(
        source="50hertz",
        source_id=source_id,
        signal_type="offshore_grid_connection",
        title=title,
        url="https://www.50hertz.com/en/example",
        published_at=None,
        capacity_mw=927.0,
        location_text="Gnewitz substation (onshore connection point)",
        geom_status="unresolved",
        attributes={"capacity_basis": "generation"},
    )


def test_first_load_inserts_then_rerun_is_unchanged():
    connection = FakeConnection()
    record = make_record()

    first = load_records(connection, [record])
    assert (first.inserted, first.updated, first.unchanged) == (1, 0, 0)

    second = load_records(connection, [record])
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 1)
    assert connection.touched == 1


def test_changed_content_updates_the_same_row():
    connection = FakeConnection()
    first = make_record(title="Original")
    load_records(connection, [first])

    second = make_record(title="Changed")
    result = load_records(connection, [second])

    assert (result.inserted, result.updated, result.unchanged) == (0, 1, 0)
    assert connection.hashes[("50hertz", "OST-6-1")] == second.content_hash


def test_different_source_ids_create_separate_rows():
    connection = FakeConnection()
    result = load_records(
        connection,
        [make_record("OST-6-1"), make_record("ostwind-2")],
    )
    assert result.inserted == 2
    assert len(connection.hashes) == 2


def test_geometry_is_inserted_with_25832_srid():
    connection = FakeConnection()
    record = make_record()
    record.geometry = GeoResult(
        status="approximate",
        matched_name="gnewitz",
        lon=12.5132459,
        lat=54.0788474,
        x_25832=459_000.0,
        y_25832=5_990_000.0,
        precision="approximate",
    )
    record.geom_status = "approximate"

    load_records(connection, [record])
    insert_sql, params = next(
        (sql, values) for sql, values in connection.queries if "INSERT INTO" in sql
    )
    assert "ST_SetSRID(ST_MakePoint(%s, %s), 25832)" in insert_sql
    assert params[8] == 459_000.0
    assert params[9] == 5_990_000.0


def test_missing_geometry_is_inserted_as_null():
    connection = FakeConnection()
    load_records(connection, [make_record()])
    insert_sql, _ = next(
        (sql, values) for sql, values in connection.queries if "INSERT INTO" in sql
    )
    assert "geom" in insert_sql
    assert "ST_SetSRID" not in insert_sql
    assert "NULL" in insert_sql
