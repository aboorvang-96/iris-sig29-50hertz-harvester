"""End-to-end orchestration tests (offline)."""

from __future__ import annotations

import pytest

from iris_harvester.config import DEFAULT_PROJECTS, ProjectSource
from iris_harvester.errors import SourceUnavailableError
from iris_harvester.harvester import Harvester
from iris_harvester.parser import FiftyHertzParser

from conftest import FIXTURES


def test_offline_run_extracts_all_four_pages(parser, geocoder):
    result = Harvester(parser, geocoder).run_offline(FIXTURES)
    assert len(result.records) == 4
    assert result.errors == []
    assert result.geom_counts == {"approximate": 4}
    assert {record.source_id for record in result.records} == {
        "OST-6-1",
        "ostwind-2",
        "ostwind-3",
        "ostwind-4",
    }


def test_missing_fixture_is_reported_and_others_continue(parser, geocoder):
    projects = (
        ProjectSource("Missing", "https://www.50hertz.com/en/missing", "missing.html"),
        DEFAULT_PROJECTS[0],
    )
    result = Harvester(parser, geocoder).run_offline(FIXTURES, projects)
    assert len(result.records) == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "SourceUnavailableError"


def test_malformed_fixture_is_reported(parser, geocoder, tmp_path):
    (tmp_path / "broken.html").write_text("<html><body>not a project page</body></html>")
    projects = (
        ProjectSource("Broken", "https://www.50hertz.com/en/broken", "broken.html"),
    )
    result = Harvester(parser, geocoder).run_offline(tmp_path, projects)
    assert result.records == []
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "ParseError"


def test_duplicate_source_id_in_one_run_is_not_silently_loaded(parser, geocoder):
    projects = (DEFAULT_PROJECTS[0], DEFAULT_PROJECTS[0])
    result = Harvester(parser, geocoder).run_offline(FIXTURES, projects)
    assert len(result.records) == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "DuplicateRecordError"


def test_live_mode_requires_a_client(parser, geocoder):
    with pytest.raises(SourceUnavailableError, match="requires an HTTP client"):
        Harvester(parser, geocoder).run_live()


def test_live_mode_uses_client_payload(parser, geocoder):
    class FakeClient:
        def get(self, url: str) -> bytes:
            project = next(p for p in DEFAULT_PROJECTS if p.url == url)
            return (FIXTURES / project.fixture).read_bytes()

    result = Harvester(parser, geocoder, client=FakeClient()).run_live()
    assert len(result.records) == 4
    assert result.errors == []


def test_parser_and_geocoder_are_not_mutated_between_runs(parser, geocoder):
    first = Harvester(parser, geocoder).run_offline(FIXTURES)
    second = Harvester(parser, geocoder).run_offline(FIXTURES)
    assert [r.content_hash for r in first.records] == [r.content_hash for r in second.records]


def test_record_contains_no_invented_publication_date(parser, geocoder):
    result = Harvester(parser, geocoder).run_offline(FIXTURES)
    assert all(record.published_at is None for record in result.records)
