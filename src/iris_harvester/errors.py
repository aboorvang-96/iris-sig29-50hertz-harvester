"""Domain errors for the harvester."""

from __future__ import annotations


class HarvesterError(Exception):
    """Base class for expected harvester failures."""


class SourceUnavailableError(HarvesterError):
    """The source could not be retrieved or is not usable."""


class RobotsDeniedError(SourceUnavailableError):
    """robots.txt forbids the requested URL for our user agent."""


class ParseError(HarvesterError):
    """The page was empty, malformed, or lacked required project fields."""


class ConfigurationError(HarvesterError):
    """Local configuration (gazetteer, paths) is invalid."""


class DatabaseLoadError(HarvesterError):
    """Records could not be loaded into PostgreSQL."""
