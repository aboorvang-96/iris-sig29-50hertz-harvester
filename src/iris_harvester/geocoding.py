"""Local gazetteer geocoding with WGS84 -> EPSG:25832 projection."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer

from .config import (
    BBOX_MAX_LAT,
    BBOX_MAX_LON,
    BBOX_MIN_LAT,
    BBOX_MIN_LON,
    TARGET_SRID,
)
from .errors import ConfigurationError
from .models import GeoResult

_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class GazetteerEntry:
    name: str
    lat: float
    lon: float
    precision: str
    source: str


class Gazetteer:
    """A deliberately small, reviewable place-name lookup.

    Matching is exact (case-insensitive, whitespace-normalized). There is no
    fuzzy matching, because a wrong town would silently create a wrong point.
    """

    def __init__(self, entries: dict[str, GazetteerEntry]):
        self._entries = entries

    @classmethod
    def from_csv(cls, path: Path) -> "Gazetteer":
        if not path.exists():
            raise ConfigurationError(f"gazetteer not found: {path}")
        entries: dict[str, GazetteerEntry] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"name", "lat", "lon"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ConfigurationError(
                    f"gazetteer {path} must contain columns: name,lat,lon"
                )
            for line_no, row in enumerate(reader, start=2):
                name = _normalize(row.get("name", ""))
                if not name:
                    continue
                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError(
                        f"{path}:{line_no}: lat/lon must be numeric"
                    ) from exc
                precision = (row.get("precision") or "exact").strip().casefold()
                if precision not in {"exact", "approximate"}:
                    raise ConfigurationError(
                        f"{path}:{line_no}: precision must be exact or approximate"
                    )
                if name in entries:
                    raise ConfigurationError(f"{path}:{line_no}: duplicate name {name!r}")
                entries[name] = GazetteerEntry(
                    name=name,
                    lat=lat,
                    lon=lon,
                    precision=precision,
                    source=(row.get("source") or "").strip(),
                )
        if not entries:
            raise ConfigurationError(f"gazetteer is empty: {path}")
        return cls(entries)

    def lookup(self, name: str | None) -> GazetteerEntry | None:
        if not name:
            return None
        return self._entries.get(_normalize(name))

    def __len__(self) -> int:
        return len(self._entries)


class Geocoder:
    """Resolve a place name and project it to the required CRS."""

    def __init__(self, gazetteer: Gazetteer):
        self._gazetteer = gazetteer
        self._transformer = Transformer.from_crs(
            "EPSG:4326", f"EPSG:{TARGET_SRID}", always_xy=True
        )

    def resolve(self, place_name: str | None) -> GeoResult:
        if not place_name:
            return GeoResult(
                status="unresolved",
                reason="no onshore place name could be extracted",
            )

        entry = self._gazetteer.lookup(place_name)
        if entry is None:
            return GeoResult(
                status="unresolved",
                reason=f"no gazetteer entry for {place_name!r}",
            )

        if not (BBOX_MIN_LAT <= entry.lat <= BBOX_MAX_LAT):
            return GeoResult(
                status="invalid",
                matched_name=entry.name,
                lon=entry.lon,
                lat=entry.lat,
                reason=(
                    f"latitude {entry.lat} outside allowed bbox "
                    f"[{BBOX_MIN_LAT}, {BBOX_MAX_LAT}]"
                ),
            )
        if not (BBOX_MIN_LON <= entry.lon <= BBOX_MAX_LON):
            return GeoResult(
                status="invalid",
                matched_name=entry.name,
                lon=entry.lon,
                lat=entry.lat,
                reason=(
                    f"longitude {entry.lon} outside allowed bbox "
                    f"[{BBOX_MIN_LON}, {BBOX_MAX_LON}]"
                ),
            )

        try:
            x, y = self._transformer.transform(entry.lon, entry.lat)
        except Exception as exc:  # pyproj raises several exception types
            return GeoResult(
                status="invalid",
                matched_name=entry.name,
                lon=entry.lon,
                lat=entry.lat,
                reason=f"projection to EPSG:{TARGET_SRID} failed: {exc}",
            )

        status = "approximate" if entry.precision == "approximate" else "resolved"
        return GeoResult(
            status=status,
            matched_name=entry.name,
            lon=entry.lon,
            lat=entry.lat,
            x_25832=x,
            y_25832=y,
            precision=entry.precision,
            reason=(
                "gazetteer precision is approximate"
                if status == "approximate"
                else None
            ),
        )


def _normalize(value: str) -> str:
    return _WS_RE.sub(" ", (value or "").strip()).casefold()
