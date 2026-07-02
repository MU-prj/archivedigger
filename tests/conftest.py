"""Fixture condivise della suite archivedigger.

Le fixture di dati (risposte di ricerca e metadati item realistici presi da
Internet Archive) vivono in tests/fixtures/ come JSON e vengono caricate da
qui, così i test unit girano veloci e offline.
"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
