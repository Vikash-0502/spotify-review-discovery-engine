"""Main processing pipeline: raw reviews → clean processed reviews."""

from dataclasses import dataclass

from collectors.keywords import is_discovery_related, passes_negative_filter
from models.database import get_session_factory, init_db
from models.schema import RawReview, Review
from processing.anonymizer import anonymize_author
from processing.dedup import DedupTracker
from processing.normalizer import normalize_platform, normalize_text, parse_posted_at, word_count
from processing.pii_scanner import contains_pii, redact_pii
from processing.report import ProcessingStats, save_processing_report
from processing.validation import validate_content, validate_platform, validate_posted_at
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessedRecord:
    raw_review_id: str
    platform: str
    content: str
    title: str | None
    rating: int | None
    posted_at: object
    anonymized_author: str
    is_discovery_related: bool
    word_count: int


def _extract_raw_fields(raw: RawReview) -> dict:
    payload = raw.raw_payload or {}
    content = payload.get("content") or ""
    title = payload.get("title")
    return {
        "content": content,
        "title": title,
        "author": payload.get("author"),
        "rating": payload.get("rating"),
        "posted_at": parse_posted_at(payload.get("posted_at")),
        "source_url": raw.source_url or payload.get("source_url"),
    }


def process_record(raw: RawReview, stats: ProcessingStats, dedup: DedupTracker) -> ProcessedRecord | None:
    platform = normalize_platform(raw.platform)
    platform_check = validate_platform(platform)
    if not platform_check.ok:
        stats.record_drop(platform_check.reason)
        return None

    fields = _extract_raw_fields(raw)
    content = normalize_text(fields["content"])
    title = normalize_text(fields["title"]) if fields.get("title") else None

    content_check = validate_content(content)
    if not content_check.ok:
        stats.record_drop(content_check.reason)
        return None

    date_check = validate_posted_at(fields["posted_at"])
    if not date_check.ok:
        stats.record_drop(date_check.reason)
        return None

    if not is_discovery_related(content, spotify_source=True):
        stats.record_drop("not_discovery_related")
        return None

    if not passes_negative_filter(content):
        stats.record_drop("negative_keyword_filter")
        return None

    if contains_pii(content) or (title and contains_pii(title)):
        stats.pii_redactions += 1
        content = redact_pii(content)
        if title:
            title = redact_pii(title)

    content_check = validate_content(content)
    if not content_check.ok:
        stats.record_drop("unusable_after_pii_redaction")
        return None

    if dedup.is_duplicate(content):
        stats.record_drop("duplicate_content")
        return None

    anonymized = anonymize_author(platform, fields.get("author"))

    return ProcessedRecord(
        raw_review_id=raw.id,
        platform=platform,
        content=content,
        title=title or None,
        rating=fields.get("rating"),
        posted_at=fields["posted_at"],
        anonymized_author=anonymized,
        is_discovery_related=True,
        word_count=word_count(content),
    )


def run_processing() -> ProcessingStats:
    init_db()
    stats = ProcessingStats()
    dedup = DedupTracker()
    session = get_session_factory()()

    try:
        raw_records = session.query(RawReview).all()
        stats.raw_total = len(raw_records)

        processed_raw_ids = {
            row[0]
            for row in session.query(Review.raw_review_id).all()
        }

        for raw in raw_records:
            if raw.id in processed_raw_ids:
                stats.already_processed += 1
                continue

            processed = process_record(raw, stats, dedup)
            if processed is None:
                continue

            session.add(
                Review(
                    raw_review_id=processed.raw_review_id,
                    platform=processed.platform,
                    content=processed.content,
                    title=processed.title,
                    rating=processed.rating,
                    posted_at=processed.posted_at,
                    anonymized_author=processed.anonymized_author,
                    is_discovery_related=processed.is_discovery_related,
                    word_count=processed.word_count,
                    language="en",
                )
            )
            stats.saved += 1
            stats.by_platform[processed.platform] = stats.by_platform.get(processed.platform, 0) + 1

        stats.duplicates_removed = dedup.duplicates_removed
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(
        "Processing complete — saved=%s dropped=%s duplicates=%s",
        stats.saved,
        stats.dropped,
        stats.duplicates_removed,
    )
    return stats
