from pathlib import Path

import pytest

from iik_bot.catalog import load_catalog
from iik_bot.storage import Storage


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
async def store(tmp_path: Path):
    storage = Storage(tmp_path / "test.sqlite3")
    await storage.open()
    try:
        yield storage
    finally:
        await storage.close()
