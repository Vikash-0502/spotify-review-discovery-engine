"""Shared PostgreSQL test fixtures."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/review_discovery_test",
)


def postgres_available(url: str = TEST_DATABASE_URL) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_url():
    if not postgres_available():
        pytest.skip(
            "PostgreSQL with pgvector is not available. "
            "Start docker compose or set TEST_DATABASE_URL."
        )
    return TEST_DATABASE_URL


@pytest.fixture
def engine(postgres_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    from utils.config import get_settings
    from models.database import get_engine, init_db, reset_engine

    get_settings.cache_clear()
    reset_engine()
    init_db()
    eng = get_engine()
    yield eng
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def db_session(engine):
    from models.database import get_session_factory

    session = get_session_factory()()
    yield session
    session.rollback()
    session.close()
