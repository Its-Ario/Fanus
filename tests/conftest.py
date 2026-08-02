import os
import sys
from pathlib import Path

import pytest
from peewee import SqliteDatabase

os.environ["QT_QPA_PLATFORM"] = "offscreen"

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def in_memory_db():
    """Provides an isolated, fast, in-memory SQLite database for testing."""
    test_db = SqliteDatabase(":memory:")
    test_db.connect()
    yield test_db
    test_db.close()
