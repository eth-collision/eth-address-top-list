import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from main import SOURCE_URL, fetch_snapshot, write_snapshot


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.requests = []

    def get(self, url, params, timeout):
        self.requests.append((url, params, timeout))
        return FakeResponse(next(self.payloads))


def item(number, balance):
    return {
        "hash": f"0x{number:040x}",
        "coin_balance": str(balance),
    }


class SnapshotTests(unittest.TestCase):
    def test_fetches_paginated_snapshot_and_sorts_returned_balances(self):
        session = FakeSession(
            [
                {
                    "items": [item(1, 200), item(2, 300)],
                    "next_page_params": {
                        "items_count": 2,
                        "hash": item(2, 0)["hash"],
                        "transactions_count": None,
                    },
                },
                {
                    "items": [item(3, 100)],
                    "next_page_params": None,
                },
            ]
        )
        self.assertEqual(
            fetch_snapshot(limit=3, delay=0, session=session),
            [item(2, 0)["hash"], item(1, 0)["hash"], item(3, 0)["hash"]],
        )
        self.assertEqual(session.requests[0], (SOURCE_URL, {}, 30))
        self.assertEqual(session.requests[1][1]["items_count"], 2)
        self.assertEqual(session.requests[1][1]["transactions_count"], "null")

    def test_skips_duplicate_address(self):
        session = FakeSession(
            [
                {
                    "items": [item(1, 200), item(1, 100), item(2, 50)],
                    "next_page_params": None,
                }
            ]
        )
        self.assertEqual(
            fetch_snapshot(limit=2, delay=0, session=session),
            [item(1, 0)["hash"], item(2, 0)["hash"]],
        )

    def test_writes_snapshot_and_matching_metadata_digest(self):
        addresses = [item(1, 0)["hash"], item(2, 0)["hash"]]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "address.txt"
            metadata = Path(directory) / "snapshot.json"
            write_snapshot(addresses, output, metadata)

            content = output.read_text(encoding="utf-8")
            details = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(details["address_count"], 2)
            self.assertEqual(details["source"], SOURCE_URL)
            self.assertEqual(
                details["sha256"], hashlib.sha256(content.encode("utf-8")).hexdigest()
            )


if __name__ == "__main__":
    unittest.main()
