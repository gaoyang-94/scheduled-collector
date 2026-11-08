"""Poll a JSON endpoint on an interval and keep a clean table."""

import argparse
import json
import sys
import time

from .http import FetchError, fetch_json
from .store import Store


def extract_items(payload, list_key=None):
    """Pull the list out of common API shapes without a config file."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if list_key and isinstance(payload.get(list_key), list):
            return payload[list_key]
        for candidate in ("data", "results", "items", "markets", "rows"):
            value = payload.get(candidate)
            if isinstance(value, list):
                return value
            if isinstance(value, dict) and isinstance(value.get(candidate), list):
                return value[candidate]
    raise ValueError("no list found in payload; pass --list-key")


def run_once(url, db, list_key=None, key_field="id", quiet=False):
    payload = fetch_json(url)
    items = extract_items(payload, list_key)
    store = Store(db)
    try:
        stats = store.upsert_many(items, key=key_field)
        total = store.count()
    finally:
        store.close()
    if not quiet:
        print(json.dumps({"fetched": len(items), **stats, "total": total}))
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Poll a JSON endpoint into SQLite")
    parser.add_argument("--url", required=True)
    parser.add_argument("--db", default="collector.db")
    parser.add_argument("--list-key", default=None)
    parser.add_argument("--key-field", default="id")
    parser.add_argument("--interval", type=int, default=900, help="seconds between runs")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)

    if args.once:
        stats = run_once(args.url, args.db, args.list_key, args.key_field)
        return 0 if stats else 1

    while True:
        started = time.time()
        try:
            run_once(args.url, args.db, args.list_key, args.key_field)
        except (FetchError, ValueError) as exc:
            print(f"run failed: {exc}", file=sys.stderr)
        time.sleep(max(1, args.interval - (time.time() - started)))


if __name__ == "__main__":
    sys.exit(main())
