"""Data structures shared by parsing, geocoding and loading."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GeoResult:
    """Result of resolving a place name through the local gazetteer."""

    status: str
    matched_name: str | None = None
    lon: float | None = None
    lat: float | None = None
    x_25832: float | None = None
    y_25832: float | None = None
    precision: str | None = None
    reason: str | None = None

    @property
    def has_geometry(self) -> bool:
        return self.x_25832 is not None and self.y_25832 is not None


@dataclass
class SignalRecord:
    """A normalized staging record, before/after database assignment."""

    source: str
    source_id: str
    signal_type: str
    title: str
    url: str
    published_at: datetime | None
    capacity_mw: float | None
    location_text: str | None
    geom_status: str
    attributes: dict[str, Any] = field(default_factory=dict)
    geometry: GeoResult | None = None

    def content_payload(self) -> dict[str, Any]:
        """Stable representation used for change detection.

        Timestamps and database identifiers are deliberately excluded so that a
        re-run of unchanged source data produces the same hash.
        """

        return {
            "source": self.source,
            "source_id": self.source_id,
            "signal_type": self.signal_type,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "capacity_mw": self.capacity_mw,
            "location_text": self.location_text,
            "geom_status": self.geom_status,
            "geometry": (
                {
                    "x_25832": self.geometry.x_25832,
                    "y_25832": self.geometry.y_25832,
                }
                if self.geometry and self.geometry.has_geometry
                else None
            ),
            "attributes": self.attributes,
        }

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(
            self.content_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_artifact(self) -> dict[str, Any]:
        """Public JSON representation written by the CLI."""

        geo = self.geometry
        return {
            "source": self.source,
            "source_id": self.source_id,
            "signal_type": self.signal_type,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "capacity_mw": self.capacity_mw,
            "location_text": self.location_text,
            "geom_status": self.geom_status,
            "geometry": (
                {
                    "srid": 25832,
                    "lon": geo.lon,
                    "lat": geo.lat,
                    "x": geo.x_25832,
                    "y": geo.y_25832,
                    "matched_name": geo.matched_name,
                    "precision": geo.precision,
                    "reason": geo.reason,
                }
                if geo
                else None
            ),
            "content_hash": self.content_hash,
            "attributes": self.attributes,
        }


@dataclass
class HarvestError:
    """A per-source failure that must remain visible in the run summary."""

    source: str
    url: str
    error_type: str
    message: str


@dataclass
class HarvestResult:
    records: list[SignalRecord] = field(default_factory=list)
    errors: list[HarvestError] = field(default_factory=list)

    @property
    def geom_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.geom_status] = counts.get(record.geom_status, 0) + 1
        return counts


@dataclass
class LoadResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged
