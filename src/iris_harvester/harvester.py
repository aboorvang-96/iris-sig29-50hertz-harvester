"""Orchestration of fetch/read, parse and geocode for all project pages."""

from __future__ import annotations

from pathlib import Path

from .client import HttpClient
from .config import DEFAULT_PROJECTS, ProjectSource
from .errors import HarvesterError, ParseError, SourceUnavailableError
from .geocoding import Geocoder
from .models import HarvestError, HarvestResult
from .parser import FiftyHertzParser


class Harvester:
    def __init__(
        self,
        parser: FiftyHertzParser,
        geocoder: Geocoder,
        client: HttpClient | None = None,
    ):
        self.parser = parser
        self.geocoder = geocoder
        self.client = client

    def run_offline(
        self,
        fixtures_dir: Path,
        projects: tuple[ProjectSource, ...] = DEFAULT_PROJECTS,
    ) -> HarvestResult:
        result = HarvestResult()
        for project in projects:
            path = fixtures_dir / project.fixture
            try:
                html = path.read_bytes()
            except OSError as exc:
                result.errors.append(
                    HarvestError(
                        source=project.name,
                        url=project.url,
                        error_type="SourceUnavailableError",
                        message=f"fixture not readable: {path} ({exc})",
                    )
                )
                continue
            self._process(project, html, result)
        return result

    def run_live(
        self,
        projects: tuple[ProjectSource, ...] = DEFAULT_PROJECTS,
    ) -> HarvestResult:
        if self.client is None:
            raise SourceUnavailableError("live mode requires an HTTP client")
        result = HarvestResult()
        for project in projects:
            try:
                html = self.client.get(project.url)
            except SourceUnavailableError as exc:
                result.errors.append(
                    HarvestError(
                        source=project.name,
                        url=project.url,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            self._process(project, html, result)
        return result

    def _process(self, project: ProjectSource, html: bytes, result: HarvestResult) -> None:
        try:
            parsed = self.parser.parse(html, project.url)
        except ParseError as exc:
            result.errors.append(
                HarvestError(
                    source=project.name,
                    url=project.url,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            return
        except HarvesterError as exc:
            result.errors.append(
                HarvestError(
                    source=project.name,
                    url=project.url,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            return

        record = self.parser.to_record(parsed)
        geometry = self.geocoder.resolve(parsed.attributes.get("geocode_name"))
        record.geometry = geometry
        record.geom_status = geometry.status

        if any(
            existing.source == record.source and existing.source_id == record.source_id
            for existing in result.records
        ):
            result.errors.append(
                HarvestError(
                    source=project.name,
                    url=project.url,
                    error_type="DuplicateRecordError",
                    message=(
                        f"duplicate source_id {record.source_id!r} in one run; "
                        "the second record was not added"
                    ),
                )
            )
            return

        result.records.append(record)
