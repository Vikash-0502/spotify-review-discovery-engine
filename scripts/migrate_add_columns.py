"""Simple DB migration helper to add new columns if they don't exist.

This script targets the local SQLite DB configured in `utils.config` and uses
PRAGMA table_info(...) to check for columns and ALTER TABLE to add them.

Run with:
    python scripts/migrate_add_columns.py
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Ensure project root is on sys.path when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.database import get_engine


def column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(text(f"PRAGMA table_info('{table}')"))
    cols = [row[1] for row in r.fetchall()]
    return column in cols


def safe_add_column(conn, table: str, column_def: str) -> bool:
    # column_def should be like "user_segment TEXT"
    column = column_def.split()[0]
    if column_exists(conn, table, column):
        print(f"Column '{column}' already exists on '{table}', skipping.")
        return False
    sql = f"ALTER TABLE {table} ADD COLUMN {column_def};"
    conn.execute(text(sql))
    print(f"Added column '{column}' to '{table}'.")
    return True


def main():
    engine = get_engine()
    with engine.begin() as conn:
        # Reviews: add user_segment
        safe_add_column(conn, "reviews", "user_segment TEXT")

        # Themes: readable_name, summary, root_cause
        safe_add_column(conn, "themes", "readable_name VARCHAR(255)")
        safe_add_column(conn, "themes", "summary TEXT")
        safe_add_column(conn, "themes", "root_cause TEXT")

    print("Migration complete.")


if __name__ == "__main__":
    main()
