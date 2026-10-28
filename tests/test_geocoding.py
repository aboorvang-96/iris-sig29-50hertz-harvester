"""Gazetteer and projection tests."""

from __future__ import annotations

import pytest

from iris_harvester.errors import ConfigurationError
from iris_harvester.geocoding import Gazetteer, Geocoder

from conftest import FIXTURES


def test_all_onshore_points_are_projected(geocoder: Geocoder):
    for name in ("Lubmin", "Gnewitz", "Stilow"):
        result = geocoder.resolve(name)
        assert result.status == "approximate"
        assert result.precision == "approximate"
        assert result.has_geometry
        assert result.x_25832 and result.y_25832


def test_lubmin_uses_the_gazetteer_coordinate(geocoder: Geocoder):
    result = geocoder.resolve("lubmin")
    assert result.matched_name == "lubmin"
    assert result.lon == 13.64847
    assert result.lat == 54.14481
    # EPSG:25832 easting/northing for this area, not WGS84 degrees.
    assert 700_000 < result.x_25832 < 900_000
    assert 5_900_000 < result.y_25832 < 6_100_000


def test_unknown_place_is_unresolved_with_reason(geocoder: Geocoder):
    result = geocoder.resolve("Atlantis")
    assert result.status == "unresolved"
    assert result.reason
    assert not result.has_geometry


def test_missing_place_name_is_unresolved(geocoder: Geocoder):
    result = geocoder.resolve(None)
    assert result.status == "unresolved"
    assert not result.has_geometry


def test_coordinate_outside_bbox_is_invalid(tmp_path, geocoder: Geocoder):
    path = tmp_path / "gazetteer.csv"
    path.write_text(
        "name,lat,lon,precision\nFarAway,60.0,13.0,exact\n",
        encoding="utf-8",
    )
    geocoder = Geocoder(Gazetteer.from_csv(path))
    result = geocoder.resolve("FarAway")
    assert result.status == "invalid"
    assert "outside allowed bbox" in result.reason
    assert not result.has_geometry


def test_non_numeric_coordinate_is_configuration_error(tmp_path):
    path = tmp_path / "gazetteer.csv"
    path.write_text("name,lat,lon\nBroken,not-a-number,13.0\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="lat/lon must be numeric"):
        Gazetteer.from_csv(path)


def test_duplicate_gazetteer_name_is_configuration_error(tmp_path):
    path = tmp_path / "gazetteer.csv"
    path.write_text(
        "name,lat,lon\nLubmin,54.1,13.6\nLubmin,54.2,13.7\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="duplicate name"):
        Gazetteer.from_csv(path)


def test_exact_entry_is_reported_as_resolved(tmp_path):
    path = tmp_path / "gazetteer.csv"
    path.write_text(
        "name,lat,lon,precision\nLubmin,54.14481,13.64847,exact\n",
        encoding="utf-8",
    )
    result = Geocoder(Gazetteer.from_csv(path)).resolve("LUBMIN")
    assert result.status == "resolved"
    assert result.precision == "exact"


def test_missing_gazetteer_file_is_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError, match="not found"):
        Gazetteer.from_csv(tmp_path / "absent.csv")


def test_shipped_gazetteer_is_small_and_explicit():
    gazetteer = Gazetteer.from_csv(FIXTURES / "gazetteer.csv")
    assert len(gazetteer) == 3
