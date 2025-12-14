"""Loader helpers for inserting cleaned data into Snowflake.

This is intentionally minimal — replace the simplistic insertion logic
with bulk copy or prepared statements for production use.
"""
import json
import os
from pathlib import Path
from typing import List
from contextlib import contextmanager

# Try to import from common if available, otherwise create a stub
try:
    from common.snowflake import get_connection
except ImportError:
    # Stub function - implement real Snowflake connection here
    @contextmanager
    def get_connection():
        """Stub connection for testing. Replace with real implementation."""
        print("Warning: Using stub Snowflake connection. Implement real connection in common.snowflake")
        yield None  # Would be conn object


def load_to_snowflake() -> bool:
    project_root = Path(__file__).resolve().parents[2]
    cleaned = project_root / "data" / "cleaned" / "sample_talks_clean.json"
    if not cleaned.exists():
        print("No cleaned data to load; skipping")
        return True
    with cleaned.open("r", encoding="utf8") as f:
        items = json.load(f)

    # Example: insert rows into a simple raw table. Update SQL and table names.
    insert_sql = "INSERT INTO raw_ted_talks (talk_id, title, transcript) VALUES (%(talk_id)s, %(title)s, %(transcript)s)"
    with get_connection() as conn:
        if conn is None:
            print("No database connection available; data would be loaded to Snowflake")
            return True
        cur = conn.cursor()
        try:
            for r in items:
                cur.execute(insert_sql, {
                    "talk_id": r.get("talk_id"),
                    "title": r.get("title"),
                    "transcript": r.get("transcript_clean") or r.get("transcript"),
                })
            conn.commit()
        finally:
            cur.close()

    print(f"Loaded {len(items)} records to Snowflake")
    return True


if __name__ == "__main__":
    load_to_snowflake()
