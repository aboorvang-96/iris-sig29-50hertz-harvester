"""robots.txt tests use the saved copy, so they run offline."""

from __future__ import annotations

import pytest

from iris_harvester.errors import RobotsDeniedError
from iris_harvester.robots import RobotsPolicy

from conftest import FIXTURES

USER_AGENT = "iris-sig29-harvester/1.0"


@pytest.fixture(scope="module")
def policy() -> RobotsPolicy:
    return RobotsPolicy.from_text(
        (FIXTURES / "robots.txt").read_text(encoding="utf-8"),
        USER_AGENT,
    )


def test_project_paths_are_allowed(policy: RobotsPolicy):
    assert policy.can_fetch(
        "https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/Ostwind2"
    )
    assert policy.can_fetch(
        "https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects/GridconnectionOST-6-1"
    )
    assert policy.can_fetch("https://www.50hertz.com/en/Grid/Griddevelopement/Offshoreprojects")


def test_disallowed_paths_stay_disallowed(policy: RobotsPolicy):
    assert not policy.can_fetch("https://www.50hertz.com/admin/")
    assert not policy.can_fetch("https://www.50hertz.com/images/logo.png")


def test_require_raises_for_disallowed_url(policy: RobotsPolicy):
    with pytest.raises(RobotsDeniedError):
        policy.require("https://www.50hertz.com/admin/")


def test_crawl_delay_for_named_agent(policy: RobotsPolicy):
    assert policy.crawl_delay() == 0.0


def test_saved_robots_has_named_crawl_delay():
    named = RobotsPolicy.from_text(
        (FIXTURES / "robots.txt").read_text(encoding="utf-8"),
        "msnbot",
    )
    assert named.crawl_delay() == 5.0
