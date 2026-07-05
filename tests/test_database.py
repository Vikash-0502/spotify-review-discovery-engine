"""Phase 1 database initialization tests."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.schema import Base  # noqa: E402


def test_init_db_creates_all_tables(engine):
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected = {table.name for table in Base.metadata.sorted_tables}
    assert expected.issubset(table_names)


def test_expected_table_count(engine):
    assert len(Base.metadata.sorted_tables) == 8


def test_reviews_table_has_indexes(engine):
    inspector = inspect(engine)
    indexes = {idx["name"] for idx in inspector.get_indexes("reviews")}
    assert "ix_reviews_posted_at" in indexes
    assert "ix_reviews_platform" in indexes
