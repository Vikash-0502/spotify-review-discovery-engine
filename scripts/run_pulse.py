#!/usr/bin/env python3
"""Run Phase 6 weekly pulse generation and delivery."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from delivery.pulse import run_weekly_pulse  # noqa: E402
from utils.logging import setup_logging  # noqa: E402


if __name__ == "__main__":
    setup_logging()

    parser = argparse.ArgumentParser(description="Run weekly pulse generation and Docs delivery")
    parser.add_argument("--dry-run", action="store_true", help="Generate and validate without external Docs MCP delivery")
    args = parser.parse_args()

    result = run_weekly_pulse(dry_run=args.dry_run)

    print("\n=== Weekly Pulse Complete ===")
    print(f"Run ID: {result.run_id}")
    print(f"Title: {result.title}")
    print(f"Source reviews considered: {result.source_review_count}")
    print(f"Sample reviews used: {result.sample_review_count}")
    print(f"Validation passed: {result.validation.is_valid}")
    if result.validation.errors:
        print("Validation errors:")
        for error in result.validation.errors:
            print(f"- {error}")
    if result.delivery:
        print(f"Delivery mode: {result.delivery.mode}")
        print(f"Delivery status: {result.delivery.status}")
        if result.delivery.document_url:
            print(f"Document URL: {result.delivery.document_url}")
    print(f"Local markdown: {result.output_path}")
