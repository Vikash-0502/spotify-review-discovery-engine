#!/usr/bin/env python3
"""Run the data processing pipeline on raw reviews."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from processing.pipeline import run_processing  # noqa: E402
from processing.report import save_processing_report  # noqa: E402
from utils.logging import get_logger, setup_logging  # noqa: E402

if __name__ == "__main__":
    setup_logging()
    logger = get_logger(__name__)
    stats = run_processing()
    save_processing_report(stats)
    logger.info("Done — saved %s processed reviews", stats.saved)
    print(f"\n=== Processing Complete ===")
    print(f"New records saved: {stats.saved}")
    print(f"Dropped: {stats.dropped}")
    print(f"Duplicates removed: {stats.duplicates_removed}")
    print(f"Report: data/processing_report.md")
