#!/usr/bin/env python3
"""Run NLP analysis on processed reviews."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.pipeline import run_analysis  # noqa: E402
from analysis.report import save_analysis_report  # noqa: E402
from utils.logging import get_logger, setup_logging  # noqa: E402

if __name__ == "__main__":
    setup_logging()
    logger = get_logger(__name__)

    parser = argparse.ArgumentParser(description="Run NLP analysis pipeline")
    parser.add_argument("--force-themes", action="store_true", help="Regenerate themes and insights")
    parser.add_argument("--min-topic-size", type=int, default=15, help="Minimum reviews per theme")
    args = parser.parse_args()

    stats = run_analysis(force_themes=args.force_themes, min_topic_size=args.min_topic_size)
    save_analysis_report(stats)

    print("\n=== Analysis Complete ===")
    print(f"Reviews analyzed: {stats.reviews_analyzed}")
    print(f"Sentiment labeled: {stats.sentiment_labeled}")
    print(f"Embeddings saved: {stats.embeddings_saved}")
    print(f"Themes created: {stats.themes_created}")
    print(f"Insights created: {stats.insights_created}")
    print(f"Quotes created: {stats.quotes_created}")
    print("Report: data/analysis_report.md")
