#!/usr/bin/env python3
"""Build a validated snapshot of Ethereum's top accounts from Etherscan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SOURCE_URL = "https://etherscan.io/accounts/{page}?ps={page_size}"


def extract_addresses(html: str) -> list[str]:
    """Extract full addresses from ranked account table rows.

    Etherscan truncates visible anchor text, so the canonical address must come
    from the link target. Restricting extraction to table rows also excludes
    unrelated addresses such as the donation link in the page footer.
    """
    soup = BeautifulSoup(html, "html.parser")
    addresses: list[str] = []

    for row in soup.select("table tbody tr"):
        for link in row.find_all("a", href=True):
            path = urlparse(link["href"]).path
            if not path.startswith("/address/"):
                continue
            candidate = path.removeprefix("/address/")
            if ADDRESS_RE.fullmatch(candidate):
                addresses.append(candidate.lower())
                break

    return addresses


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
            "User-Agent": (
                "eth-address-top-list/2.0 "
                "(+https://github.com/eth-collision/eth-address-top-list)"
            )
        }
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_snapshot(
    pages: int = 100,
    page_size: int = 100,
    delay: float = 0.25,
    session: requests.Session | None = None,
    transport: str = "http",
) -> list[str]:
    if transport not in {"http", "selenium"}:
        raise ValueError(f"unsupported transport: {transport}")

    if transport == "selenium":
        return fetch_snapshot_with_browser(pages, page_size, delay)

    client = session or build_session()
    return collect_snapshot(
        pages,
        page_size,
        delay,
        lambda url: fetch_http(client, url),
    )


def fetch_http(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def fetch_snapshot_with_browser(
    pages: int,
    page_size: int,
    delay: float,
) -> list[str]:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.FirefoxOptions()
    options.add_argument("-headless")
    browser = webdriver.Firefox(options=options)

    def fetch_page(url: str) -> str:
        browser.get(url)
        WebDriverWait(browser, 30).until(
            lambda driver: len(
                driver.find_elements(
                    By.CSS_SELECTOR,
                    "table tbody tr a[href^='/address/']",
                )
            )
            >= page_size
        )
        return browser.page_source

    try:
        return collect_snapshot(pages, page_size, delay, fetch_page)
    finally:
        browser.quit()


def collect_snapshot(
    pages: int,
    page_size: int,
    delay: float,
    fetch_page: Callable[[str], str],
) -> list[str]:
    addresses: list[str] = []

    for page in range(1, pages + 1):
        url = SOURCE_URL.format(page=page, page_size=page_size)
        page_addresses = extract_addresses(fetch_page(url))

        if len(page_addresses) != page_size:
            raise RuntimeError(
                f"page {page} returned {len(page_addresses)} complete addresses; "
                f"expected {page_size}. Refusing to replace the last good snapshot."
            )

        addresses.extend(page_addresses)
        print(f"Fetched page {page}/{pages}: {len(addresses)} addresses", flush=True)
        if page < pages and delay:
            time.sleep(delay)

    expected = pages * page_size
    if len(addresses) != expected or len(set(addresses)) != expected:
        raise RuntimeError(
            "snapshot contains missing or duplicate addresses; "
            "refusing to replace the last good snapshot"
        )
    return addresses


def write_snapshot(addresses: list[str], output: Path, metadata: Path) -> None:
    invalid = [address for address in addresses if not ADDRESS_RE.fullmatch(address)]
    if invalid:
        raise ValueError(f"snapshot contains {len(invalid)} invalid addresses")

    content = "".join(f"{address}\n" for address in addresses)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    snapshot_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata_content = {
        "address_count": len(addresses),
        "generated_at": snapshot_time,
        "sha256": digest,
        "source": "https://etherscan.io/accounts",
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
    parser.add_argument("--pages", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument(
        "--transport",
        choices=("http", "selenium"),
        default="http",
        help="page transport; GitHub Actions uses selenium because Etherscan blocks runner HTTP requests",
    )
    parser.add_argument("--output", type=Path, default=Path("address.txt"))
    parser.add_argument("--metadata", type=Path, default=Path("snapshot.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    addresses = fetch_snapshot(
        args.pages,
        args.page_size,
        args.delay,
        transport=args.transport,
    )
    write_snapshot(addresses, args.output, args.metadata)
    print(f"Published {len(addresses)} validated addresses to {args.output}")


if __name__ == "__main__":
    main()
