#!/usr/bin/env python3
"""Initialize the database schema."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.database import init_db  # noqa: E402
from utils.logging import get_logger, setup_logging  # noqa: E402

if __name__ == "__main__":
    setup_logging()
    logger = get_logger(__name__)
    init_db()
    logger.info("Database tables created successfully.")
