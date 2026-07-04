#!/usr/bin/env python3
"""Redact residual PII (@handles, email, phone) in stored review and quote text."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.database import get_session_factory, init_db  # noqa: E402
from models.schema import Insight, Quote, Review  # noqa: E402
from processing.pii_scanner import contains_pii, redact_pii  # noqa: E402
from utils.logging import setup_logging  # noqa: E402


def remediate_text_fields(*, dry_run: bool) -> dict[str, int]:
    init_db()
    session = get_session_factory()()
    stats = {"reviews_updated": 0, "quotes_updated": 0, "insights_updated": 0}

    try:
        for review in session.query(Review).all():
            if contains_pii(review.content):
                if not dry_run:
                    review.content = redact_pii(review.content)
                stats["reviews_updated"] += 1

        for quote in session.query(Quote).all():
            if contains_pii(quote.excerpt):
                if not dry_run:
                    quote.excerpt = redact_pii(quote.excerpt)
                stats["quotes_updated"] += 1

        for insight in session.query(Insight).all():
            if contains_pii(insight.summary):
                if not dry_run:
                    insight.summary = redact_pii(insight.summary)
                stats["insights_updated"] += 1

        if not dry_run:
            session.commit()
    finally:
        session.close()

    return stats


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Redact residual PII in processed text fields")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing changes")
    args = parser.parse_args()
    stats = remediate_text_fields(dry_run=args.dry_run)
    mode = "Would update" if args.dry_run else "Updated"
    print(f"{mode}: {stats['reviews_updated']} reviews, {stats['quotes_updated']} quotes, {stats['insights_updated']} insights")
