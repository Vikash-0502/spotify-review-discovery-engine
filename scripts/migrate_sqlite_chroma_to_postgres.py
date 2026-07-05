#!/usr/bin/env python3
"""Migrate legacy SQLite + Chroma data into PostgreSQL with pgvector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from models.database import init_db, reset_engine
from models.schema import Base
from utils.config import get_settings
from utils.logging import setup_logging, get_logger
logger = get_logger(__name__)

TABLES_IN_ORDER = [
    "raw_reviews",
    "reviews",
    "themes",
    "review_themes",
    "insights",
    "quotes",
    "weekly_pulses",
]


def _copy_table(source: Session, target: Session, table_name: str) -> int:
    table = Base.metadata.tables[table_name]
    rows = source.execute(table.select()).mappings().all()
    if not rows:
        return 0
    target.execute(table.delete())
    target.execute(table.insert(), rows)
    return len(rows)


def migrate_relational_data(source_url: str, target_url: str) -> dict[str, int]:
    source_engine = create_engine(source_url, future=True)
    target_engine = create_engine(target_url, future=True)

    source = sessionmaker(bind=source_engine)()
    target = sessionmaker(bind=target_engine)()
    counts: dict[str, int] = {}

    try:
        for table_name in TABLES_IN_ORDER:
            if table_name not in inspect(source_engine).get_table_names():
                continue
            counts[table_name] = _copy_table(source, target, table_name)
            logger.info("Copied %s rows from %s", counts[table_name], table_name)
        target.commit()
    finally:
        source.close()
        target.close()
        source_engine.dispose()
        target_engine.dispose()

    return counts


def _coerce_chroma_ids(raw_ids) -> list[str]:
    if raw_ids is None:
        return []
    return [str(review_id) for review_id in list(raw_ids)]


def _coerce_chroma_embeddings(raw_embeddings) -> list[list[float]]:
    """Normalize Chroma get() embeddings to a list of float vectors.

    Latest ChromaDB returns a 2D NumPy array for batch results, which cannot be
    used with ``value or []`` because multi-element arrays are ambiguous in bool
    context.
    """
    import numpy as np

    if raw_embeddings is None:
        return []

    arr = np.asarray(raw_embeddings, dtype=np.float32)
    if arr.size == 0:
        return []

    if arr.ndim == 1:
        return [arr.astype(float).tolist()]
    if arr.ndim == 2:
        return [row.astype(float).tolist() for row in arr]

    raise ValueError(f"Unexpected Chroma embedding shape: {arr.shape}")


def _insert_embedding_rows(session, rows: list[dict], *, batch_size: int = 500) -> int:
    from sqlalchemy.dialects.postgresql import insert

    from models.schema import ReviewEmbedding

    if not rows:
        return 0

    inserted = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        stmt = insert(ReviewEmbedding).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ReviewEmbedding.review_id],
            set_={
                "embedding_model": stmt.excluded.embedding_model,
                "embedding_vector": stmt.excluded.embedding_vector,
            },
        )
        session.execute(stmt)
        inserted += len(batch)
    return inserted


def migrate_chroma_embeddings(chroma_path: str, collection_name: str, target_url: str) -> int:
    try:
        import chromadb
    except ImportError as exc:
        raise SystemExit(
            "chromadb is required for Chroma migration only. Install with: pip install chromadb"
        ) from exc

    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        raise SystemExit(
            f"Chroma collection '{collection_name}' not found at {chroma_path}: {exc}"
        ) from exc

    result = collection.get(include=["embeddings"])
    ids = _coerce_chroma_ids(result.get("ids"))
    embedding_vectors = _coerce_chroma_embeddings(result.get("embeddings"))

    if len(ids) == 0:
        return 0
    if len(embedding_vectors) == 0:
        logger.warning("Chroma returned %s ids but no embeddings; skipping vector migration", len(ids))
        return 0
    if len(ids) != len(embedding_vectors):
        logger.warning(
            "Chroma id/embedding count mismatch (%s ids, %s embeddings); migrating the overlapping prefix",
            len(ids),
            len(embedding_vectors),
        )
        limit = min(len(ids), len(embedding_vectors))
        ids = ids[:limit]
        embedding_vectors = embedding_vectors[:limit]

    settings = get_settings()
    reset_engine()
    target_engine = create_engine(target_url, future=True)
    session = sessionmaker(bind=target_engine)()

    try:
        rows = [
            {
                "review_id": review_id,
                "embedding_model": settings.embedding_model,
                "embedding_vector": vector,
            }
            for review_id, vector in zip(ids, embedding_vectors)
        ]
        migrated = _insert_embedding_rows(session, rows)
        session.commit()
        return migrated
    finally:
        session.close()
        target_engine.dispose()


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Migrate SQLite + Chroma into PostgreSQL/pgvector")
    parser.add_argument(
        "--source-sqlite",
        default=str(PROJECT_ROOT / "data" / "reviews.db"),
        help="Path to legacy SQLite database file",
    )
    parser.add_argument(
        "--source-chroma",
        default=str(PROJECT_ROOT / "data" / "chroma"),
        help="Path to legacy Chroma directory",
    )
    parser.add_argument(
        "--chroma-collection",
        default="spotify_reviews",
        help="Legacy Chroma collection name",
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Target PostgreSQL URL (defaults to DATABASE_URL from settings)",
    )
    parser.add_argument(
        "--skip-chroma",
        action="store_true",
        help="Skip Chroma embedding migration",
    )
    args = parser.parse_args()

    target_url = args.target_url or get_settings().database_url
    source_url = f"sqlite:///{Path(args.source_sqlite).resolve().as_posix()}"

    if not Path(args.source_sqlite).exists():
        raise SystemExit(f"SQLite source not found: {args.source_sqlite}")

    logger.info("Initializing target PostgreSQL schema")
    reset_engine()
    import os

    os.environ["DATABASE_URL"] = target_url
    get_settings.cache_clear()
    init_db()

    logger.info("Copying relational tables from SQLite")
    counts = migrate_relational_data(source_url, target_url)
    print("\n=== Relational Migration Complete ===")
    for table, count in counts.items():
        print(f"  {table}: {count:,} rows")

    if not args.skip_chroma and Path(args.source_chroma).exists():
        logger.info("Copying embeddings from Chroma into pgvector")
        migrated = migrate_chroma_embeddings(args.source_chroma, args.chroma_collection, target_url)
        print(f"  review_embeddings: {migrated:,} vectors")
    else:
        print("  review_embeddings: skipped (run analysis to rebuild vectors if needed)")

    print(f"\nTarget database: {target_url}")


if __name__ == "__main__":
    main()
