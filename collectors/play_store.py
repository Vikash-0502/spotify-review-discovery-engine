"""Google Play Store review collector for Spotify."""

from datetime import timezone

from google_play_scraper import Sort, reviews

from collectors.base import CollectedRecord, SourceStats
from collectors.keywords import is_discovery_related, passes_negative_filter
from utils.logging import get_logger

logger = get_logger(__name__)

APP_ID = "com.spotify.music"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.spotify.music"


def collect_play_store(
    max_reviews: int = 50000,
    min_matched: int = 1200,
    country: str = "us",
) -> tuple[list[CollectedRecord], SourceStats]:
    stats = SourceStats(platform="play_store")
    records: list[CollectedRecord] = []
    seen_ids: set[str] = set()

    countries = [country]
    if country == "us":
        countries.append("gb")

    sort_orders = [Sort.NEWEST, Sort.MOST_RELEVANT]

    for c in countries:
        for sort in sort_orders:
            continuation_token = None
            batch_size = 2000

            while stats.fetched < max_reviews and stats.matched < min_matched:
                try:
                    if continuation_token:
                        batch, continuation_token = reviews(
                            APP_ID,
                            continuation_token=continuation_token,
                        )
                    else:
                        batch, continuation_token = reviews(
                            APP_ID,
                            lang="en",
                            country=c,
                            sort=sort,
                            count=batch_size,
                        )
                except Exception as exc:
                    stats.errors.append(f"{c}/{sort}: {exc}")
                    logger.warning("Play Store fetch failed for %s/%s: %s", c, sort, exc)
                    break

                if not batch:
                    break

                stats.fetched += len(batch)

                for item in batch:
                    review_id = str(item.get("reviewId") or "")
                    if not review_id or review_id in seen_ids:
                        continue
                    seen_ids.add(review_id)

                    content = (item.get("content") or "").strip()
                    if not is_discovery_related(content, spotify_source=True):
                        continue
                    if not passes_negative_filter(content):
                        continue

                    posted_at = item.get("at")
                    if posted_at and posted_at.tzinfo is None:
                        posted_at = posted_at.replace(tzinfo=timezone.utc)
                    if not posted_at:
                        continue

                    stats.matched += 1
                    stats.track_dates(posted_at)

                    records.append(
                        CollectedRecord(
                            platform="play_store",
                            external_id=review_id,
                            content=content,
                            posted_at=posted_at,
                            source_url=PLAY_STORE_URL,
                            author=item.get("userName"),
                            rating=item.get("score"),
                            metadata={
                                "thumbs_up": item.get("thumbsUpCount"),
                                "app_version": item.get("reviewCreatedVersion"),
                                "country": c,
                            },
                        )
                    )

                if not continuation_token:
                    break

                if stats.matched >= min_matched:
                    break

    logger.info("Play Store: fetched=%s matched=%s", stats.fetched, stats.matched)
    return records, stats


def collect_play_store_sample(count: int = 100) -> tuple[list[CollectedRecord], SourceStats]:
    """Fetch a small sample (for tests)."""
    batch, _ = reviews(APP_ID, lang="en", country="us", sort=Sort.NEWEST, count=count)
    stats = SourceStats(platform="play_store")
    records = []
    for item in batch:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        posted_at = item.get("at")
        if posted_at and posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        if not posted_at:
            continue
        review_id = str(item.get("reviewId") or f"sample_{len(records)}")
        records.append(
            CollectedRecord(
                platform="play_store",
                external_id=review_id,
                content=content,
                posted_at=posted_at,
                source_url=PLAY_STORE_URL,
                author=item.get("userName"),
                rating=item.get("score"),
            )
        )
        stats.matched += 1
        stats.fetched += 1
        stats.track_dates(posted_at)
    return records, stats
