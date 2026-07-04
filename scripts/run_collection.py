#!/usr/bin/env python3
"""Run data collectors and save results to the database."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from collectors.app_store import collect_app_store  # noqa: E402
from collectors.base import save_json_backup, save_records  # noqa: E402
from collectors.play_store import collect_play_store  # noqa: E402
from collectors.reddit_collector import collect_reddit  # noqa: E402
from collectors.report import build_report, save_report  # noqa: E402
from collectors.spotify_community import collect_spotify_community  # noqa: E402
from utils.logging import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)

COLLECTORS = {
    "play_store": collect_play_store,
    "app_store": collect_app_store,
    "reddit": collect_reddit,
    "spotify_community": collect_spotify_community,
}


def run_source(name: str, **kwargs):
    if name == "play_store":
        return collect_play_store(
            max_reviews=kwargs.get("play_store_max", 50000),
            min_matched=kwargs.get("play_store_min_matched", 1200),
        )
    if name == "app_store":
        return collect_app_store(how_many=kwargs.get("app_store_max", 500))
    if name == "reddit":
        return collect_reddit(limit_per_query=kwargs.get("reddit_limit", 100))
    if name == "spotify_community":
        return collect_spotify_community(max_per_term=kwargs.get("community_topics", 200))
    raise ValueError(f"Unknown source: {name}")


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Collect public Spotify discovery feedback")
    parser.add_argument(
        "--sources",
        default="play_store,app_store,reddit,spotify_community",
        help="Comma-separated list of sources to collect",
    )
    parser.add_argument("--play-store-max", type=int, default=50000)
    parser.add_argument("--play-store-min-matched", type=int, default=1200)
    parser.add_argument("--app-store-max", type=int, default=500)
    parser.add_argument("--reddit-limit", type=int, default=100)
    parser.add_argument("--community-topics", type=int, default=50)
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    run_stats = []

    kwargs = {
        "play_store_max": args.play_store_max,
        "play_store_min_matched": args.play_store_min_matched,
        "app_store_max": args.app_store_max,
        "reddit_limit": args.reddit_limit,
        "community_topics": args.community_topics,
    }

    for source in sources:
        logger.info("Starting collector: %s", source)
        try:
            records, stats = run_source(source, **kwargs)
            saved, skipped = save_records(records)
            stats.saved = saved
            stats.skipped_duplicates = skipped
            save_json_backup(records, f"{source}_latest.json")
            run_stats.append(stats)
            logger.info(
                "%s done — matched=%s saved=%s skipped=%s",
                source,
                stats.matched,
                saved,
                skipped,
            )
        except Exception as exc:
            logger.exception("Collector failed: %s", source)
            from collectors.base import SourceStats

            failed = SourceStats(platform=source, errors=[str(exc)])
            run_stats.append(failed)

    report = build_report(run_stats)
    save_report(report)

    print("\n=== Collection Complete ===")
    print(f"Total records in database: {report['total_records']}")
    for platform, count in report["by_platform"].items():
        print(f"  {platform}: {count}")
    print(f"Report: data/collection_report.md")


if __name__ == "__main__":
    main()
