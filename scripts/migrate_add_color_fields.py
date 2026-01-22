#!/usr/bin/env python3
"""Migration script to add vehicle color fields to the listings table.

Run this script to add exterior_color, interior_color, and interior_material
columns to an existing database.

Usage:
    python scripts/migrate_add_color_fields.py [--db PATH]
"""

import argparse
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/i4_scout.db")


def get_existing_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    """Get existing column names for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def migrate(db_path: Path) -> None:
    """Add color columns to the listings table."""
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        existing_columns = get_existing_columns(cursor, "listings")

        columns_to_add = [
            ("exterior_color", "VARCHAR(100)"),
            ("interior_color", "VARCHAR(100)"),
            ("interior_material", "VARCHAR(100)"),
        ]

        added = []
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE listings ADD COLUMN {col_name} {col_type}"
                )
                added.append(col_name)
                print(f"Added column: {col_name}")
            else:
                print(f"Column already exists: {col_name}")

        if added:
            conn.commit()
            print(f"\nMigration complete. Added {len(added)} column(s).")
        else:
            print("\nNo migration needed. All columns already exist.")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add vehicle color fields to the listings table"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args()

    migrate(args.db)
