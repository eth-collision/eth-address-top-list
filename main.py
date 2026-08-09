#!/usr/bin/env python3
"""Build a validated snapshot of Ethereum's top accounts from Blockscout."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SOURCE_URL = "https://eth.blockscout.com/api/v2/addresses"


def build_session() -> requests.Session:
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": (
                "eth-address-top-list/3.0 "
                "(+https://github.com/eth-collision/eth-address-top-list)"
            ),
        }
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_snapshot(
    limit: int = 10_000,
    delay: float = 0.1,
    session: requests.Session | None = None,
) -> list[str]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    client = session or build_session()
    params: dict[str, str | int] = {}
    ranked_addresses: list[tuple[int, str]] = []
    seen: set[str] = set()

    while len(ranked_addresses) < limit:
        response = client.get(SOURCE_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise RuntimeError("Blockscout returned an empty or malformed address page")

        for item in items:
            address = item.get("hash", "").lower()
            balance_text = item.get("coin_balance")
            if not ADDRESS_RE.fullmatch(address):
                raise RuntimeError(f"Blockscout returned an invalid address: {address!r}")
            try:
                balance = int(balance_text)
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    f"Blockscout returned an invalid balance for {address}"
                ) from error
            if balance < 0:
                raise RuntimeError(f"Blockscout returned a negative balance for {address}")
            if address in seen:
                continue

            seen.add(address)
            ranked_addresses.append((balance, address))
            if len(ranked_addresses) == limit:
                break

        print(f"Fetched {len(ranked_addresses)}/{limit} unique addresses", flush=True)
        if len(ranked_addresses) == limit:
            break

        next_page = payload.get("next_page_params")
        if not isinstance(next_page, dict) or not next_page:
            raise RuntimeError(
                f"Blockscout pagination ended after {len(ranked_addresses)} unique addresses"
            )
        # `requests` drops query parameters whose value is None, but Blockscout
        # uses an explicit `transactions_count=null` as part of some cursors.
        params = {
            key: "null" if value is None else value
            for key, value in next_page.items()
        }
        if delay:
            time.sleep(delay)

    # Balances can change while pagination is in progress, so establish the
    # final ordering from the values returned during this refresh.
    ranked_addresses.sort(key=lambda item: (-item[0], item[1]))
    return [address for _, address in ranked_addresses]


def write_snapshot(addresses: list[str], output: Path, metadata: Path) -> None:
    invalid = [address for address in addresses if not ADDRESS_RE.fullmatch(address)]
    if invalid:
        raise ValueError(f"snapshot contains {len(invalid)} invalid addresses")
    if len(addresses) != len(set(addresses)):
        raise ValueError("snapshot contains duplicate addresses")

    content = "".join(f"{address}\n" for address in addresses)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    snapshot_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata_content = {
        "address_count": len(addresses),
        "generated_at": snapshot_time,
        "sha256": digest,
        "source": SOURCE_URL,
    }

    output_tmp = output.with_suffix(output.suffix + ".tmp")
    metadata_tmp = metadata.with_suffix(metadata.suffix + ".tmp")
    output_tmp.write_text(content, encoding="utf-8")
    metadata_tmp.write_text(
        json.dumps(metadata_content, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_tmp.replace(output)
    metadata_tmp.replace(metadata)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--output", type=Path, default=Path("address.txt"))
    parser.add_argument("--metadata", type=Path, default=Path("snapshot.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    addresses = fetch_snapshot(args.limit, args.delay)
    write_snapshot(addresses, args.output, args.metadata)
    print(f"Published {len(addresses)} validated addresses to {args.output}")


if __name__ == "__main__":
    main()
