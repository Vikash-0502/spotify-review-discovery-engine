"""Reddit discussion collector for Spotify discovery feedback."""

from datetime import datetime, timezone

import praw

from collectors.base import CollectedRecord, SourceStats
from collectors.keywords import (
    is_discovery_related,
    is_spotify_context,
    passes_negative_filter,
)
from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

SUBREDDITS = ["spotify", "truespotify", "spotifyplaylists"]

SEARCH_QUERIES = [
    "discover weekly OR recommendations OR algorithm",
    '"same songs" OR repetitive OR "smart shuffle"',
    "discovery OR recommendations OR algorithm",
    "daylist OR release radar OR daily mix",
    "private session OR explore OR genre",
    "find new music OR music discovery",
]

MIN_COMMENT_LENGTH = 20
MAX_COMMENTS_PER_POST = 50


def _reddit_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.reddit_client_id
        and settings.reddit_client_secret
        and settings.reddit_client_id != "your_client_id"
    )


def _to_record(
    *,
    external_id: str,
    content: str,
    posted_at: datetime,
    source_url: str,
    title: str | None,
    author: str | None,
    subreddit: str,
    record_type: str,
) -> CollectedRecord:
    return CollectedRecord(
        platform="reddit",
        external_id=external_id,
        content=content,
        title=title,
        posted_at=posted_at,
        source_url=source_url,
        author=author,
        metadata={"subreddit": subreddit, "record_type": record_type},
    )


def collect_reddit(limit_per_query: int = 100) -> tuple[list[CollectedRecord], SourceStats]:
    stats = SourceStats(platform="reddit")
    records: list[CollectedRecord] = []
    seen_ids: set[str] = set()

    if not _reddit_configured():
        stats.errors.append("Reddit API credentials not configured in .env — skipped")
        logger.warning("Reddit skipped: add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to .env")
        return records, stats

    settings = get_settings()
    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
        ratelimit_seconds=300,
    )

    for sub_name in SUBREDDITS:
        subreddit = reddit.subreddit(sub_name)
        for query in SEARCH_QUERIES:
            try:
                submissions = subreddit.search(query, limit=limit_per_query, time_filter="all")
                for submission in submissions:
                    stats.fetched += 1
                    post_text = f"{submission.title}\n{submission.selftext or ''}".strip()
                    post_url = f"https://reddit.com{submission.permalink}"
                    post_time = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)

                    if post_text and len(post_text) >= MIN_COMMENT_LENGTH:
                        if is_spotify_context(post_text, sub_name) and is_discovery_related(post_text):
                            if passes_negative_filter(post_text):
                                ext_id = f"reddit_post_{submission.id}"
                                if ext_id not in seen_ids:
                                    seen_ids.add(ext_id)
                                    stats.matched += 1
                                    stats.track_dates(post_time)
                                    records.append(
                                        _to_record(
                                            external_id=ext_id,
                                            content=post_text,
                                            posted_at=post_time,
                                            source_url=post_url,
                                            title=submission.title,
                                            author=str(submission.author) if submission.author else None,
                                            subreddit=sub_name,
                                            record_type="post",
                                        )
                                    )

                    submission.comments.replace_more(limit=0)
                    comment_count = 0
                    for comment in submission.comments.list():
                        if comment_count >= MAX_COMMENTS_PER_POST:
                            break
                        stats.fetched += 1
                        body = (comment.body or "").strip()
                        if len(body) < MIN_COMMENT_LENGTH:
                            continue
                        if not is_spotify_context(body, sub_name):
                            continue
                        if not is_discovery_related(body):
                            continue
                        if not passes_negative_filter(body):
                            continue

                        ext_id = f"reddit_comment_{comment.id}"
                        if ext_id in seen_ids:
                            continue
                        seen_ids.add(ext_id)
                        comment_time = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
                        stats.matched += 1
                        stats.track_dates(comment_time)
                        records.append(
                            _to_record(
                                external_id=ext_id,
                                content=body,
                                posted_at=comment_time,
                                source_url=f"{post_url}{comment.id}/",
                                title=submission.title,
                                author=str(comment.author) if comment.author else None,
                                subreddit=sub_name,
                                record_type="comment",
                            )
                        )
                        comment_count += 1

            except Exception as exc:
                stats.errors.append(f"r/{sub_name} query '{query}': {exc}")
                logger.warning("Reddit error r/%s: %s", sub_name, exc)

    logger.info("Reddit: fetched=%s matched=%s", stats.fetched, stats.matched)
    return records, stats
