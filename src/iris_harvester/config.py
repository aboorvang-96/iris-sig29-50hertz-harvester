"""Configuration for the IRIS-SIG-29 50Hertz harvester."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
DEFAULT_GAZETTEER_PATH = DEFAULT_FIXTURES_DIR / "gazetteer.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "out" / "signals.jsonl"

SOURCE = "50hertz"
SIGNAL_TYPE = "offshore_grid_connection"

# The brief endpoint (https://www.50hertz.com/de/Netzanschluss) was unavailable
# when verified. These English project pages are the justified alternative.
DEFAULT_PROJECTS: tuple["ProjectSource", ...] = ()


@dataclass(frozen=True)
class ProjectSource:
    """One source page and the local fixture captured for offline runs."""

    name: str
    url: str
    fixture: str


DEFAULT_PROJECTS = (
    ProjectSource(
        name="OST-6-1",
        url="https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/GridconnectionOST-6-1",
        fixture="OST-6-1.html",
    ),
    ProjectSource(
        name="Ostwind 2",
        url="https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind2",
        fixture="Ostwind 2.html",
    ),
    ProjectSource(
        name="Ostwind 3",
        url="https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind3",
        fixture="Ostwind 3.html",
    ),
    ProjectSource(
        name="Ostwind 4",
        url="https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind4",
        fixture="Ostwind 4.html",
    ),
)

# WGS84 bounding box used to reject obviously wrong gazetteer coordinates.
BBOX_MIN_LAT = 47.0
BBOX_MAX_LAT = 56.0
BBOX_MIN_LON = 5.0
BBOX_MAX_LON = 16.0

TARGET_SRID = 25832


@dataclass(frozen=True)
class Settings:
    """Runtime settings, populated from environment variables where relevant."""

    database_url: str | None
    request_delay_seconds: float
    http_timeout_seconds: float
    http_retries: int
    user_agent: str

    @classmethod
    def from_env(cls, database_url: str | None = None) -> "Settings":
        return cls(
            database_url=database_url or os.getenv("IRIS_DATABASE_URL") or None,
            request_delay_seconds=_float_env("IRIS_REQUEST_DELAY_SECONDS", 2.0),
            http_timeout_seconds=_float_env("IRIS_HTTP_TIMEOUT_SECONDS", 20.0),
            http_retries=_int_env("IRIS_HTTP_RETRIES", 3),
            user_agent=os.getenv("IRIS_USER_AGENT", "iris-sig29-harvester/1.0"),
        )


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
