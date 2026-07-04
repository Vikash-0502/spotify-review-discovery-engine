"""Apple App Store review collector for Spotify (iTunes RSS API)."""

import hashlib
from datetime import datetime, timezone

import httpx

from collectors.base import CollectedRecord, SourceStats
from collectors.keywords import is_discovery_related, passes_negative_filter
from utils.logging import get_logger

logger = get_logger(__name__)

APP_ID = "324684580"
APP_STORE_URL = "https://apps.apple.com/us/app/spotify-music-and-podcasts/id324684580"
MAX_PAGES = 10


def _label(entry: dict, key: str) -> str:
    value = entry.get(key, {})
    if isinstance(value, dict):
        return (value.get("label") or "").strip()
    return ""


def _author(entry: dict) -> str:
    author = entry.get("author", {})
    if isinstance(author, dict):
        name = author.get("name", {})
        if isinstance(name, dict):
            return (name.get("label") or "").strip()
    return ""


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _fetch_page(client: httpx.Client, page: int, sort: str) -> list[dict]:
    url = (
        f"https://itunes.apple.com/us/rss/customerreviews/"
        f"page={page}/id={APP_ID}/sortby={sort}/json"
    )
    response = client.get(url, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    entry = data.get("feed", {}).get("entry")
    if not entry:
        return []
    if isinstance(entry, dict):
        return [entry]
    return entry


def collect_app_store(how_many: int = 500, country: str = "us") -> tuple[list[CollectedRecord], SourceStats]:
    stats = SourceStats(platform="app_store")
    records: list[CollectedRecord] = []
    seen_ids: set[str] = set()

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) review-discovery-engine/1.0"}
    sorts = ["mostrecent", "mosthelpful"]

    with httpx.Client(headers=headers) as client:
        for sort in sorts:
            for page in range(1, MAX_PAGES + 1):
                if stats.fetched >= how_many:
                    break
                try:
                    entries = _fetch_page(client, page, sort)
                except Exception as exc:
                    stats.errors.append(f"page {page}/{sort}: {exc}")
                    logger.warning("App Store page %s/%s failed: %s", page, sort, exc)
                    break

                if not entries:
                    break

                for entry in entries:
                    stats.fetched += 1
                    if not _label(entry, "im:rating"):
                        continue

                    title = _label(entry, "title")
                    body = _label(entry, "content")
                    content = f"{title}\n{body}".strip() if title else body
                    if len(content) < 20:
                        continue

                    if not is_discovery_related(content, spotify_source=True):
                        continue
                    if not passes_negative_filter(content):
                        continue

                    review_id = _label(entry, "id")
                    external_id = review_id or hashlib.sha256(content.encode()).hexdigest()[:16]
                    if external_id in seen_ids:
                        continue
                    seen_ids.add(external_id)

                    posted_at = _parse_date(_label(entry, "updated"))
                    if not posted_at:
                        continue

                    rating_raw = _label(entry, "im:rating")
                    rating = int(rating_raw) if rating_raw.isdigit() else None

                    stats.matched += 1
                    stats.track_dates(posted_at)

                    link = entry.get("link", {})
                    href = link.get("attributes", {}).get("href") if isinstance(link, dict) else None

                    records.append(
                        CollectedRecord(
                            platform="app_store",
                            external_id=external_id,
                            content=content,
                            title=title or None,
                            posted_at=posted_at,
                            source_url=href or APP_STORE_URL,
                            author=_author(entry),
                            rating=rating,
                            metadata={"country": country, "sort": sort},
                        )
                    )

    logger.info("App Store: fetched=%s matched=%s", stats.fetched, stats.matched)
    return records, stats
