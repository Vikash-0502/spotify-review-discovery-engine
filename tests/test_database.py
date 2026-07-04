"""Phase 1 database initialization tests."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.database import get_engine, init_db, reset_engine  # noqa: E402
from models.schema import Base  # noqa: E402


@pytest.fixture
def engine(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    from utils.config import get_settings

    get_settings.cache_clear()
    reset_engine()
    yield get_engine()
    reset_engine()
    get_settings.cache_clear()


def test_init_db_creates_all_tables(engine):
    init_db()
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected = {table.name for table in Base.metadata.sorted_tables}
    assert expected.issubset(table_names)


def test_expected_table_count(engine):
    init_db()
    assert len(Base.metadata.sorted_tables) == 8


def test_reviews_table_has_indexes(engine):
    init_db()
    inspector = inspect(engine)
    indexes = {idx["name"] for idx in inspector.get_indexes("reviews")}
    assert "ix_reviews_posted_at" in indexes
    assert "ix_reviews_platform" in indexes
