import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from main import collect_snapshot, extract_addresses, write_snapshot


class SnapshotTests(unittest.TestCase):
    def test_extracts_full_address_from_href_not_truncated_text(self):
        address = "0x00000000219ab540356cbb839cbe05303d7705fa"
        html = f"""
        <table><tbody><tr><td>1</td><td>
          <a href='/address/{address}'><span>0x000000...3d7705Fa</span></a>
        </td></tr></tbody></table>
        <footer><a href='/address/0x1111111111111111111111111111111111111111'>donate</a></footer>
        """
        self.assertEqual(extract_addresses(html), [address])

    def test_ignores_truncated_and_invalid_links(self):
        html = """
        <table><tbody><tr>
          <td><a href='/address/0x1234...abcd'>truncated</a></td>
        </tr></tbody></table>
        """
        self.assertEqual(extract_addresses(html), [])

    def test_writes_snapshot_and_matching_metadata_digest(self):
        addresses = [
            "0x0000000000000000000000000000000000000001",
            "0x0000000000000000000000000000000000000002",
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "address.txt"
            metadata = Path(directory) / "snapshot.json"
            write_snapshot(addresses, output, metadata)

            content = output.read_text(encoding="utf-8")
            details = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(details["address_count"], 2)
            self.assertEqual(
                details["sha256"], hashlib.sha256(content.encode("utf-8")).hexdigest()
            )

    def test_collect_snapshot_rejects_incomplete_page(self):
        html = """
        <table><tbody><tr>
          <td><a href='/address/0x0000000000000000000000000000000000000001'>one</a></td>
        </tr></tbody></table>
        """
        with self.assertRaisesRegex(RuntimeError, "expected 2"):
            collect_snapshot(1, 2, 0, lambda _url: html)


if __name__ == "__main__":
    unittest.main()
