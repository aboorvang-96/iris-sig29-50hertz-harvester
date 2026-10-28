"""Parsing tests against the four captured pages."""

from __future__ import annotations

import pytest

from iris_harvester.config import DEFAULT_PROJECTS
from iris_harvester.errors import ParseError
from iris_harvester.parser import FiftyHertzParser

from conftest import FIXTURES


@pytest.mark.parametrize(
    "fixture,source_id,capacity,basis,generation,deadline_count",
    [
        ("OST-6-1.html", "OST-6-1", 927.0, "generation", 927.0, 1),
        ("Ostwind 2.html", "ostwind-2", 750.0, "transmission", 725.0, 3),
        ("Ostwind 3.html", "ostwind-3", 300.0, "generation", 300.0, 1),
        ("Ostwind 4.html", "ostwind-4", 2000.0, "transmission", 1000.0, 1),
    ],
)
def test_fixture_pages_extract_expected_fields(
    parser: FiftyHertzParser,
    fixture: str,
    source_id: str,
    capacity: float,
    basis: str,
    generation: float,
    deadline_count: int,
):
    project = next(p for p in DEFAULT_PROJECTS if p.fixture == fixture)
    parsed = parser.parse((FIXTURES / fixture).read_bytes(), project.url)

    assert parsed.source_id == source_id
    assert parsed.title
    assert parsed.url == project.url
    assert parsed.capacity_mw == capacity
    assert parsed.attributes["capacity_basis"] == basis
    assert parsed.attributes["generation_capacity_mw"] == generation
    assert len(parsed.attributes["completion_deadlines"]) == deadline_count
    assert parsed.attributes["geocode_name"]
    assert parsed.attributes["onshore_connection_point"]
    assert parsed.attributes["offshore_location"]


def test_publication_date_is_always_null(parser: FiftyHertzParser):
    for project in DEFAULT_PROJECTS:
        parsed = parser.parse((FIXTURES / project.fixture).read_bytes(), project.url)
        record = parser.to_record(parsed)
        assert record.published_at is None
        assert parsed.attributes["publication_date"] is None
        assert "published_at" in parsed.attributes["missing_fields"]


def test_completion_dates_are_iso_and_in_attributes(parser: FiftyHertzParser):
    parsed = parser.parse(
        (FIXTURES / "Ostwind 2.html").read_bytes(),
        DEFAULT_PROJECTS[1].url,
    )
    dates = [item["date"] for item in parsed.attributes["completion_deadlines"]]
    assert dates == ["2023-09-30", "2023-12-31", "2024-09-30"]
    assert parsed.attributes["completion_deadlines"][0]["designation"] == "OST-2-1"


def test_url_is_taken_from_the_page_form_action(parser: FiftyHertzParser):
    parsed = parser.parse(
        (FIXTURES / "Ostwind 3.html").read_bytes(),
        "https://www.50hertz.com/some/other/url",
    )
    assert parsed.url == (
        "https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind3"
    )


def test_empty_document_fails_loudly(parser: FiftyHertzParser):
    with pytest.raises(ParseError, match="empty"):
        parser.parse("", "https://www.50hertz.com/x")


def test_page_without_table_fails_loudly(parser: FiftyHertzParser):
    html = "<html><body><main><h1>Some project</h1><p>No data here.</p></main></body></html>"
    with pytest.raises(ParseError, match="no data table"):
        parser.parse(html, "https://www.50hertz.com/x")


def test_missing_capacity_is_visible_not_invented(parser: FiftyHertzParser):
    html = """
    <html><body><main><h1>Ostwind 99</h1>
      <table>
        <tr><td>Location of the wind farm</td><td>North of Rügen</td></tr>
        <tr><td>Onshore point of common coupling</td><td>Lubmin substation</td></tr>
      </table>
    </main></body></html>
    """
    parsed = parser.parse(html, "https://www.50hertz.com/en/Grid/x/Ostwind99")
    assert parsed.capacity_mw is None
    assert "capacity_mw" in parsed.attributes["missing_fields"]
    assert parsed.attributes["capacity_basis"] is None


def test_unknown_layout_fails_instead_of_emitting_empty_record(parser: FiftyHertzParser):
    html = "<html><body><main><h1>Ostwind 99</h1><table><tr><td>Hello</td><td>World</td></tr></table></main></body></html>"
    with pytest.raises(ParseError, match="no recognizable"):
        parser.parse(html, "https://www.50hertz.com/x")
