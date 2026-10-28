"""HTTP client tests: robots, retries, status handling, empty bodies."""

from __future__ import annotations

import pytest
import requests

from iris_harvester.client import HttpClient
from iris_harvester.config import Settings
from iris_harvester.errors import RobotsDeniedError, SourceUnavailableError

ROBOTS_URL = "https://www.50hertz.com/robots.txt"
PAGE_URL = "https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind2"
ROBOTS_OK = b"User-agent: *\nAllow: /\n"


class FakeResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content


class FakeSession:
    def __init__(self, responses: dict[str, list[object]]):
        self.headers: dict[str, str] = {}
        self.responses = {url: list(items) for url, items in responses.items()}
        self.calls: list[str] = []

    def get(self, url: str, timeout: float):
        self.calls.append(url)
        items = self.responses.get(url)
        if not items:
            raise AssertionError(f"unexpected request to {url}")
        item = items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def settings(**overrides) -> Settings:
    values = dict(
        database_url=None,
        request_delay_seconds=2.0,
        http_timeout_seconds=5.0,
        http_retries=3,
        user_agent="iris-sig29-harvester/1.0",
    )
    values.update(overrides)
    return Settings(**values)


def test_retries_transient_status_then_succeeds():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, ROBOTS_OK)],
            PAGE_URL: [FakeResponse(503, b""), FakeResponse(200, b"<html>ok</html>")],
        }
    )
    sleeps: list[float] = []
    client = HttpClient(settings(), session=session, sleep=sleeps.append, clock=lambda: 0.0)

    assert client.get(PAGE_URL) == b"<html>ok</html>"
    assert session.calls == [ROBOTS_URL, PAGE_URL, PAGE_URL]
    assert sleeps  # throttling / backoff occurred


def test_retries_network_error_then_succeeds():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, ROBOTS_OK)],
            PAGE_URL: [requests.ConnectionError("reset"), FakeResponse(200, b"<html>ok</html>")],
        }
    )
    client = HttpClient(settings(), session=session, sleep=lambda _: None, clock=lambda: 0.0)
    assert client.get(PAGE_URL) == b"<html>ok</html>"


def test_exhausted_retries_raise_source_unavailable():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, ROBOTS_OK)],
            PAGE_URL: [FakeResponse(500, b""), FakeResponse(500, b""), FakeResponse(500, b"")],
        }
    )
    client = HttpClient(settings(), session=session, sleep=lambda _: None, clock=lambda: 0.0)
    with pytest.raises(SourceUnavailableError, match="after 3 attempt"):
        client.get(PAGE_URL)
    assert session.calls.count(PAGE_URL) == 3


def test_client_404_is_not_retried():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, ROBOTS_OK)],
            PAGE_URL: [FakeResponse(404, b"not found")],
        }
    )
    client = HttpClient(settings(), session=session, sleep=lambda _: None, clock=lambda: 0.0)
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        client.get(PAGE_URL)
    assert session.calls.count(PAGE_URL) == 1


def test_robots_disallow_blocks_page_request():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, b"User-agent: *\nDisallow: /en/\n")],
        }
    )
    client = HttpClient(settings(), session=session, sleep=lambda _: None, clock=lambda: 0.0)
    with pytest.raises(RobotsDeniedError):
        client.get(PAGE_URL)
    assert PAGE_URL not in session.calls


def test_empty_page_body_raises():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, ROBOTS_OK)],
            PAGE_URL: [FakeResponse(200, b"")],
        }
    )
    client = HttpClient(settings(), session=session, sleep=lambda _: None, clock=lambda: 0.0)
    with pytest.raises(SourceUnavailableError, match="empty response"):
        client.get(PAGE_URL)


def test_unavailable_robots_fails_closed():
    session = FakeSession({ROBOTS_URL: [FakeResponse(500, b"")] * 3})
    client = HttpClient(settings(), session=session, sleep=lambda _: None, clock=lambda: 0.0)
    with pytest.raises(SourceUnavailableError, match="robots.txt"):
        client.get(PAGE_URL)


def test_request_delay_is_applied_between_requests():
    session = FakeSession(
        {
            ROBOTS_URL: [FakeResponse(200, ROBOTS_OK)],
            PAGE_URL: [FakeResponse(200, b"<html>ok</html>")],
        }
    )
    sleeps: list[float] = []
    client = HttpClient(
        settings(request_delay_seconds=2.5),
        session=session,
        sleep=sleeps.append,
        clock=lambda: 0.0,
    )
    client.get(PAGE_URL)
    assert pytest.approx(2.5) in sleeps
