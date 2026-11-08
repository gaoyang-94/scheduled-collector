"""SQLite storage with upsert semantics.

Rows are keyed by a stable id, so a re-run updates instead of duplicating.
That is what keeps a 15-minute poll from turning the table into a log of
duplicates nobody can query.
"""

import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    first_seen  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    runs        INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_items_updated ON items(updated_at);
"""


class Store:
    def __init__(self, path: str = "collector.db"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_many(self, items, key: str = "id", now=None) -> dict:
        """Insert or update rows; returns counts of inserted/updated."""
        now = time.time() if now is None else now
        inserted = updated = 0
        with self.conn:
            for item in items:
                item_id = str(item.get(key) or item.get("q") or "")[:200]
                if not item_id:
                    continue
                row = self.conn.execute("SELECT id FROM items WHERE id = ?", (item_id,)).fetchone()
                if row:
                    self.conn.execute(
                        "UPDATE items SET payload = ?, updated_at = ?, runs = runs + 1 WHERE id = ?",
                        (json.dumps(item, ensure_ascii=False), now, item_id),
                    )
                    updated += 1
                else:
                    self.conn.execute(
                        "INSERT INTO items (id, payload, first_seen, updated_at, runs) VALUES (?, ?, ?, ?, 1)",
                        (item_id, json.dumps(item, ensure_ascii=False), now, now),
                    )
                    inserted += 1
        return {"inserted": inserted, "updated": updated}

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
