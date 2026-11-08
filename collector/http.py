"""HTTP fetching with retries, backoff and jitter.

The only interesting decision here: retry the things that are worth retrying
(timeouts, 429, 5xx) and fail fast on the things that are not (400, 401, 404).
Retrying a 404 for ten minutes just hides a broken URL.
"""

import json
import random
import time
import urllib.error
import urllib.request

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
DEFAULT_UA = "scheduled-collector/0.1 (+https://github.com/gaoyang-94/scheduled-collector)"


class FetchError(RuntimeError):
    """Raised when a request cannot be completed after all retries."""


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    """Exponential backoff with full jitter, capped.

    attempt is 1-based: attempt=1 is the wait before the second try.
    """
    raw = min(cap, base * (2 ** (attempt - 1)))
    return random.uniform(0, raw)


def fetch_json(
    url: str,
    timeout: float = 10.0,
    retries: int = 3,
    headers=None,
    sleep=time.sleep,
):
    """GET a URL and parse JSON, retrying transient failures."""
    last_error = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA, **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", "replace")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            last_error = FetchError(f"HTTP {exc.code} for {url}")
            if exc.code not in RETRY_STATUS:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = FetchError(f"{type(exc).__name__} for {url}: {exc}")

        if attempt < retries:
            sleep(backoff_delay(attempt))
    raise last_error or FetchError(f"failed: {url}")
