"""robots.txt handling for the live fetch path."""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

from .errors import RobotsDeniedError


class RobotsPolicy:
    def __init__(self, parser: RobotFileParser, user_agent: str):
        self._parser = parser
        self._user_agent = user_agent

    @classmethod
    def from_text(cls, text: str, user_agent: str) -> "RobotsPolicy":
        parser = RobotFileParser()
        parser.set_url("https://www.50hertz.com/robots.txt")
        parser.parse(text.splitlines())
        return cls(parser, user_agent)

    def can_fetch(self, url: str) -> bool:
        return self._parser.can_fetch(self._user_agent, url)

    def require(self, url: str) -> None:
        if not self.can_fetch(url):
            raise RobotsDeniedError(f"robots.txt does not permit fetching {url}")

    def crawl_delay(self) -> float:
        delay = self._parser.crawl_delay(self._user_agent)
        return float(delay) if delay else 0.0
