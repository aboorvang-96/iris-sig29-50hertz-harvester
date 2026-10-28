"""HTML parser for the 50Hertz offshore grid-connection project pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .config import SIGNAL_TYPE, SOURCE
from .errors import ParseError
from .models import SignalRecord

_WS_RE = re.compile(r"\s+")
_DATE_FORMATS = ("%d/%m/%Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d")
_POWER_RE = re.compile(r"([\d][\d.,]*)\s*(gigawatts?|gw|megawatts?|mw)\b", re.IGNORECASE)
_GENERATION_RE = re.compile(
    r"(?:output of|capacity of|target capacity of)\s+"
    r"(?:approximately\s+|about\s+)?([\d][\d.,]*)\s*"
    r"(gigawatts?|gw|megawatts?|mw)\b",
    re.IGNORECASE,
)
_TRANSMISSION_RE = re.compile(
    r"(?:transmit|transport)[^.]{0,100}?([\d][\d.,]*)\s*"
    r"(gigawatts?|gw|megawatts?|mw)\b",
    re.IGNORECASE,
)
_OST_CODE_RE = re.compile(r"\bOST-\d+-\d+\b", re.IGNORECASE)
_PROJECT_CODE_RE = re.compile(r"\bOST-\d+-\d+\b", re.IGNORECASE)
_OSTWIND_RE = re.compile(r"\bostwind\s+(\d+)\b", re.IGNORECASE)


@dataclass
class TableRow:
    cells: list[str]

    @property
    def key(self) -> str:
        return self.cells[0] if self.cells else ""

    @property
    def value(self) -> str:
        return self.cells[1] if len(self.cells) > 1 else ""


@dataclass
class ParsedPage:
    """Fields extracted from one page, before geocoding."""

    source_id: str
    title: str
    url: str
    capacity_mw: float | None
    location_text: str | None
    attributes: dict[str, Any] = field(default_factory=dict)


class FiftyHertzParser:
    """Parse a saved or live 50Hertz project page.

    The parser deliberately requires a project heading, a data table and at
    least one recognized project field. A page that returns a cookie banner,
    an error page, or a redesigned layout therefore fails loudly instead of
    producing an empty record.
    """

    def parse(self, html: str | bytes, source_url: str) -> ParsedPage:
        if html is None:
            raise ParseError("empty document")
        if isinstance(html, bytes):
            if not html.strip():
                raise ParseError("empty document")
            soup = BeautifulSoup(html, "lxml")
        else:
            if not html.strip():
                raise ParseError("empty document")
            soup = BeautifulSoup(html, "lxml")

        main = soup.find("main") or soup.body
        if main is None:
            raise ParseError("document has no body")

        heading = main.find("h1") or soup.find("h1")
        if heading is None:
            raise ParseError("no project heading (h1) found")
        title = _clean(heading.get_text(" ", strip=True))
        if not title:
            raise ParseError("project heading is empty")

        rows = _table_rows(main)
        if not rows:
            raise ParseError("no data table found")

        url = _canonical_url(soup, source_url)
        source_id = _source_id(title, url)

        offshore_label, offshore_value = _find_pair(
            rows, ("location",), excludes=("onshore",)
        ) or (None, None)
        onshore_value = (
            _find_pair(rows, ("onshore", "point of common coupling"))[1]
            if _find_pair(rows, ("onshore", "point of common coupling"))
            else None
        )
        if onshore_value is None:
            onshore_value = (
                _find_pair(rows, ("onshore", "connection point"))[1]
                if _find_pair(rows, ("onshore", "connection point"))
                else None
            )

        capacity_text, capacity_key = _capacity_cell(rows)
        prose = " ".join(_clean(p.get_text(" ", strip=True)) for p in main.find_all("p"))

        transmission = _first_power(_TRANSMISSION_RE, prose)
        generation = _first_power(_GENERATION_RE, prose)
        table_capacity = _power_from_text(capacity_text) if capacity_text else None

        capacity_mw: float | None
        capacity_basis: str | None
        capacity_source: str | None
        if capacity_key and "transmission" in capacity_key.casefold() and table_capacity:
            capacity_mw = table_capacity
            capacity_basis = "transmission"
            capacity_source = "table"
        elif table_capacity is not None:
            capacity_mw = table_capacity
            if generation is not None and generation == table_capacity:
                capacity_basis = "generation"
            else:
                capacity_basis = "published_capacity"
            capacity_source = "table"
        elif transmission is not None:
            capacity_mw = transmission
            capacity_basis = "transmission"
            capacity_source = "prose"
        elif generation is not None:
            capacity_mw = generation
            capacity_basis = "generation"
            capacity_source = "prose"
        else:
            capacity_mw = None
            capacity_basis = None
            capacity_source = None

        voltage = _find_pair(rows, ("voltage",)) or (None, None)
        voltage_value = _voltage_value(voltage[1]) if voltage[1] else None
        if voltage_value is None:
            voltage_value = _first_voltage(prose)
        route = _find_pair(rows, ("route length",)) or _find_pair(rows, ("cable length",)) or (
            None,
            None,
        )
        operator = _find_pair(rows, ("operator",)) or (None, None)
        status = _find_pair(rows, ("status of",)) or (None, None)

        completion = _completion_deadlines(rows)

        place = _place_name(onshore_value) if onshore_value else None
        location_text = _location_text(onshore_value, offshore_value)

        attributes: dict[str, Any] = {
            "project_name": title,
            "onshore_connection_point": onshore_value,
            "offshore_location_label": offshore_label,
            "offshore_location": offshore_value,
            "geocode_name": place,
            "capacity_basis": capacity_basis,
            "capacity_source": capacity_source,
            "capacity_source_text": capacity_text,
            "generation_capacity_mw": generation,
            "voltage_level": voltage_value,
            "voltage_source_text": voltage[1],
            "route_length": route[1],
            "operator": operator[1],
            "approval_status": status[1],
            "completion_deadlines": completion,
            "publication_date": None,
            "publication_date_note": "not stated on the source page",
            "page_title": _clean(soup.title.get_text(" ", strip=True)) if soup.title else None,
        }
        missing = [
            name
            for name, value in (
                ("published_at", None),
                ("capacity_mw", capacity_mw),
                ("location_text", location_text),
                ("completion_deadlines", completion or None),
                ("voltage_level", voltage_value),
                ("route_length", route[1]),
                ("operator", operator[1]),
                ("onshore_connection_point", onshore_value),
                ("offshore_location", offshore_value),
            )
            if value is None
        ]
        attributes["missing_fields"] = missing

        if not any((capacity_mw, onshore_value, offshore_value, completion)):
            raise ParseError("no recognizable project fields found")

        return ParsedPage(
            source_id=source_id,
            title=title,
            url=url,
            capacity_mw=capacity_mw,
            location_text=location_text,
            attributes=attributes,
        )

    def to_record(self, parsed: ParsedPage) -> SignalRecord:
        return SignalRecord(
            source=SOURCE,
            source_id=parsed.source_id,
            signal_type=SIGNAL_TYPE,
            title=parsed.title,
            url=parsed.url,
            published_at=None,
            capacity_mw=parsed.capacity_mw,
            location_text=parsed.location_text,
            geom_status="unresolved",
            attributes=parsed.attributes,
        )


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text.replace("\xa0", " ")).strip()


def _table_rows(main: Any) -> list[TableRow]:
    rows: list[TableRow] = []
    for table in main.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [
                _clean(cell.get_text(" ", strip=True))
                for cell in tr.find_all(["td", "th"])
            ]
            if any(cells):
                rows.append(TableRow(cells))
    return rows


def _find_pair(
    rows: list[TableRow],
    keywords: tuple[str, ...],
    excludes: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    for row in rows:
        if len(row.cells) < 2:
            continue
        key = row.key.casefold()
        if all(word in key for word in keywords) and not any(word in key for word in excludes):
            if row.value:
                return row.key, row.value
    return None


def _capacity_cell(rows: list[TableRow]) -> tuple[str | None, str | None]:
    for row in rows:
        if len(row.cells) < 2:
            continue
        key = row.key.casefold()
        if "capacity" in key and row.value:
            return row.value, row.key
    return None, None


def _normalize_number(raw: str) -> float | None:
    text = raw.strip().replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _power_from_text(text: str) -> float | None:
    match = _POWER_RE.search(text)
    if not match:
        return None
    value = _normalize_number(match.group(1))
    if value is None:
        return None
    unit = match.group(2).casefold()
    return value * 1000 if unit.startswith("g") else value


def _first_power(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if not match:
        return None
    value = _normalize_number(match.group(1))
    if value is None:
        return None
    unit = match.group(2).casefold()
    return value * 1000 if unit.startswith("g") else value


def _parse_date(text: str) -> str | None:
    candidate = _clean(text)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _completion_deadlines(rows: list[TableRow]) -> list[dict[str, str]]:
    deadlines: list[dict[str, str]] = []
    seen: set[tuple[str | None, str]] = set()

    for row in rows:
        if len(row.cells) >= 2 and "completion" in row.key.casefold():
            date = _parse_date(row.value)
            if date:
                item = {"date": date}
                key = (None, date)
                if key not in seen:
                    seen.add(key)
                    deadlines.append(item)

    for row in rows:
        if len(row.cells) < 3:
            continue
        code = next(
            (cell for cell in row.cells if _OST_CODE_RE.fullmatch(cell.strip())),
            None,
        )
        if not code:
            continue
        date = next((_parse_date(cell) for cell in reversed(row.cells) if _parse_date(cell)), None)
        if not date:
            continue
        key = (code.upper(), date)
        if key in seen:
            continue
        seen.add(key)
        item = {"designation": code.upper(), "date": date}
        codes = [cell for cell in row.cells if cell and cell != code and not _parse_date(cell)]
        descriptions = [cell for cell in codes if not cell.startswith("Expected ")]
        if descriptions:
            item["description"] = descriptions[0]
        deadlines.append(item)

    return deadlines


def _canonical_url(soup: BeautifulSoup, source_url: str) -> str:
    form = soup.find("form", id="Form")
    action = form.get("action") if form else None
    if action:
        return urljoin(source_url, str(action)).rstrip("/")
    return source_url.rstrip("/")


def _source_id(title: str, url: str) -> str:
    code = _PROJECT_CODE_RE.search(title)
    if code:
        return code.group(0).upper()
    ostwind = _OSTWIND_RE.search(title)
    if ostwind:
        return f"ostwind-{ostwind.group(1)}"
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[^a-z0-9]+", "-", slug.casefold()).strip("-")
    return slug or "unknown"


def _place_name(onshore_value: str) -> str | None:
    text = _clean(onshore_value)
    lowered = text.casefold()
    if " at " in lowered:
        text = text[lowered.rindex(" at ") + 4 :]
    elif lowered.startswith("near "):
        text = text[5:]
    text = re.sub(r"\s+(substation|converter)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^substation\s+(with\s+converter\s+)?", "", text, flags=re.IGNORECASE)
    text = text.strip(" ,.;:-")
    return text or None


def _voltage_value(text: str) -> str:
    match = re.search(r"\d[\d.,]*\s*(?:kilovolts?|kv)\b(?:[^/;]*)?", text, re.IGNORECASE)
    return _clean(match.group(0)) if match else _clean(text)


def _first_voltage(text: str) -> str | None:
    match = re.search(r"\d[\d.,]*\s*(?:kilovolts?|kv)\b", text, re.IGNORECASE)
    return _clean(match.group(0)) if match else None


def _location_text(onshore: str | None, offshore: str | None) -> str | None:
    parts: list[str] = []
    if onshore:
        parts.append(f"{onshore} (onshore connection point)")
    if offshore:
        parts.append(f"offshore: {offshore}")
    return "; ".join(parts) if parts else None
