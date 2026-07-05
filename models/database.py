"""Database engine and session management."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from models.schema import Base
from utils.config import get_settings
from utils.exceptions import DatabaseError
from utils.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def is_postgresql(database_url: str) -> bool:
    return database_url.startswith("postgresql")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not is_postgresql(settings.database_url):
            raise DatabaseError(
                "PostgreSQL is required. Set DATABASE_URL to a postgresql+psycopg:// connection string."
            )
        _engine = create_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _session_factory


def reset_engine() -> None:
    """Reset engine and session factory (for tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_db() -> None:
    """Create pgvector extension and all database tables."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized at %s", get_settings().database_url)
    except Exception as exc:
        raise DatabaseError(f"Failed to initialize database: {exc}") from exc


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    with get_session() as session:
        yield session
