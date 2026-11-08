# scheduled-collector

A polling collector that survives the night: retries what is worth retrying,
fails fast on what is not, and stores results with upsert semantics so a
15-minute poll does not turn your table into a pile of duplicates.

Zero dependencies. Standard library only.

## Why this exists

Most scrapers are written for the demo. They work until:

- the API returns `429` for two minutes,
- a request hangs and the next run overlaps with the previous one,
- the same item is inserted 96 times a day because nothing deduplicates.

This is the smallest useful version of the collector I actually run: one
entry point, one table, retry policy that distinguishes transient from
permanent failures, and a systemd unit that restarts and then gives up loudly.

## Install

```bash
git clone https://github.com/gaoyang-94/scheduled-collector
cd scheduled-collector
python3 -m unittest discover -s tests -v
```

## Use

```bash
# one pass
python3 -m collector.cli --url https://api.example.com/items --db items.db --once

# poll every 15 minutes
python3 -m collector.cli --url https://api.example.com/items --db items.db --interval 900
```

Output per run:

```json
{"fetched": 297, "inserted": 12, "updated": 285, "total": 297}
```

Point it at a different API shape with `--list-key items` or `--key-field slug`.

## What is handled, and why

| Problem | Handling |
|---|---|
| `429` / `5xx` / timeout | retried with exponential backoff + full jitter, `base=0.5s`, `cap=30s` |
| `400` / `401` / `404` | fail immediately — retrying a broken URL hides the bug |
| Duplicate rows | primary key on the item id, `UPDATE ... runs = runs + 1` |
| Restart storms | systemd `StartLimitBurst=5`, then the unit stays failed and visible |
| Silent death | every run prints a JSON line you can alert on |

## Files

```
collector/http.py    retry policy, backoff, fetch_json
collector/store.py   SQLite schema + upsert
collector/cli.py     polling loop, payload shape detection
systemd/             unit template with restart limits
tests/               backoff, fail-fast, upsert, payload shapes
```

## License

MIT
