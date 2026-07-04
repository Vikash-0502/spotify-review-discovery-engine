"""Shared helpers for saving collected records."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from models.database import get_session_factory, init_db
from models.schema import RawReview
from utils.config import PROJECT_ROOT
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CollectedRecord:
    platform: str
    external_id: str
    content: str
    posted_at: datetime
    source_url: str | None = None
    title: str | None = None
    author: str | None = None
    rating: int | None = None
    metadata: dict = field(default_factory=dict)

    def to_raw_payload(self) -> dict:
        return {
            "content": self.content,
            "title": self.title,
            "posted_at": self.posted_at.isoformat(),
            "source_url": self.source_url,
            "author": self.author,
            "rating": self.rating,
            **self.metadata,
        }


@dataclass
class SourceStats:
    platform: str
    fetched: int = 0
    matched: int = 0
    saved: int = 0
    skipped_duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    date_start: datetime | None = None
    date_end: datetime | None = None

    def track_dates(self, posted_at: datetime) -> None:
        if self.date_start is None or posted_at < self.date_start:
            self.date_start = posted_at
        if self.date_end is None or posted_at > self.date_end:
            self.date_end = posted_at


def save_records(records: list[CollectedRecord]) -> tuple[int, int]:
    """Save records to raw_reviews. Returns (saved, skipped_duplicates)."""
    init_db()
    saved = 0
    skipped = 0
    session = get_session_factory()()
    try:
        for record in records:
            exists = (
                session.query(RawReview)
                .filter_by(platform=record.platform, external_id=record.external_id)
                .first()
            )
            if exists:
                skipped += 1
                continue

            session.add(
                RawReview(
                    platform=record.platform,
                    external_id=record.external_id,
                    source_url=record.source_url,
                    raw_payload=record.to_raw_payload(),
                )
            )
            saved += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("Saved %s records (%s duplicates skipped)", saved, skipped)
    return saved, skipped


def save_json_backup(records: list[CollectedRecord], filename: str) -> Path:
    """Save a JSON backup under data/raw/."""
    out_dir = PROJECT_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    payload = [
        {
            "platform": r.platform,
            "external_id": r.external_id,
            "source_url": r.source_url,
            **r.to_raw_payload(),
        }
        for r in records
    ]
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def count_raw_by_platform(session: Session) -> dict[str, int]:
    rows = session.query(RawReview.platform).all()
    counts: dict[str, int] = {}
    for (platform,) in rows:
        counts[platform] = counts.get(platform, 0) + 1
    return counts
