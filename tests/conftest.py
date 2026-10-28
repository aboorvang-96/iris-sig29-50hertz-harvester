from pathlib import Path

import pytest

from iris_harvester.geocoding import Gazetteer, Geocoder
from iris_harvester.parser import FiftyHertzParser

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def parser() -> FiftyHertzParser:
    return FiftyHertzParser()


@pytest.fixture(scope="session")
def geocoder() -> Geocoder:
    return Geocoder(Gazetteer.from_csv(FIXTURES / "gazetteer.csv"))
