"""HTTP client with robots.txt enforcement, throttling and retries."""

from __future__ import annotations

import time
from collections.abc import Callable

import requests

from .config import Settings
from .errors import SourceUnavailableError
from .robots import RobotsPolicy

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(
        self,
        settings: Settings,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", settings.user_agent)
        self._sleep = sleep
        self._clock = clock
        self._robots: RobotsPolicy | None = None
        self._last_request_at: float | None = None

    @property
    def robots_url(self) -> str:
        return "https://www.50hertz.com/robots.txt"

    def get(self, url: str) -> bytes:
        policy = self._get_robots()
        policy.require(url)
        response = self._request_with_retries(url)
        if not response.content:
            raise SourceUnavailableError(f"empty response body from {url}")
        return response.content

    def _get_robots(self) -> RobotsPolicy:
        if self._robots is not None:
            return self._robots
        response = self._request_with_retries(self.robots_url)
        if not response.content:
            raise SourceUnavailableError(
                "robots.txt was empty; refusing to crawl without a policy"
            )
        text = response.content.decode("utf-8", errors="replace")
        self._robots = RobotsPolicy.from_text(text, self.settings.user_agent)
        return self._robots

    def _request_with_retries(self, url: str) -> requests.Response:
        attempts = max(1, self.settings.http_retries)
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            self._throttle()
            try:
                response = self.session.get(
                    url,
                    timeout=self.settings.http_timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise SourceUnavailableError(
                        f"HTTP {response.status_code} for {url}"
                    )
                else:
                    return response

            if attempt < attempts:
                self._sleep(min(2 ** (attempt - 1), 8))

        raise SourceUnavailableError(
            f"failed to fetch {url} after {attempts} attempt(s): {last_error}"
        )

    def _throttle(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            delay = self.settings.request_delay_seconds
            if self._robots is not None:
                delay = max(delay, self._robots.crawl_delay())
            remaining = delay - (now - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._clock()
