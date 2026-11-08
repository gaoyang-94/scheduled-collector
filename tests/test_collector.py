import os
import tempfile
import unittest

from collector.cli import extract_items
from collector.http import FetchError, backoff_delay, fetch_json
from collector.store import Store


class BackoffTests(unittest.TestCase):
    def test_grows_with_attempts(self):
        small = [backoff_delay(1) for _ in range(50)]
        large = [backoff_delay(4) for _ in range(50)]
        self.assertLess(max(small), max(large))

    def test_is_capped(self):
        for _ in range(100):
            self.assertLessEqual(backoff_delay(20), 30.0)


class FetchTests(unittest.TestCase):
    def test_non_retryable_status_fails_fast(self):
        calls = {"n": 0}

        def fake_urlopen(*args, **kwargs):
            calls["n"] += 1
            import urllib.error
            raise urllib.error.HTTPError("http://x", 404, "nope", {}, None)

        import collector.http as mod
        original = mod.urllib.request.urlopen
        mod.urllib.request.urlopen = fake_urlopen
        try:
            with self.assertRaises(FetchError):
                fetch_json("http://x", sleep=lambda s: None)
            self.assertEqual(calls["n"], 1)
        finally:
            mod.urllib.request.urlopen = original


class ExtractTests(unittest.TestCase):
    def test_list_payload(self):
        self.assertEqual(extract_items([{"id": 1}]), [{"id": 1}])

    def test_nested_data(self):
        self.assertEqual(extract_items({"data": [{"id": 2}]}), [{"id": 2}])

    def test_list_key_wins(self):
        payload = {"items": [{"id": 3}], "data": [{"id": 9}]}
        self.assertEqual(extract_items(payload, "items"), [{"id": 3}])

    def test_raises_on_unknown_shape(self):
        with self.assertRaises(ValueError):
            extract_items({"ok": True})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = Store(self.tmp.name)

    def tearDown(self):
        self.store.close()
        os.unlink(self.tmp.name)

    def test_second_run_updates_instead_of_duplicating(self):
        first = self.store.upsert_many([{"id": "a", "price": 1}])
        second = self.store.upsert_many([{"id": "a", "price": 2}])
        self.assertEqual(first, {"inserted": 1, "updated": 0})
        self.assertEqual(second, {"inserted": 0, "updated": 1})
        self.assertEqual(self.store.count(), 1)

    def test_rows_without_id_are_skipped(self):
        stats = self.store.upsert_many([{"price": 1}])
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(self.store.count(), 0)


if __name__ == "__main__":
    unittest.main()
