# Ethereum top-address snapshot

A weekly, validated snapshot of the top 10,000 Ethereum accounts by ETH balance,
as listed by [Etherscan](https://etherscan.io/accounts).

## Data

- [`address.txt`](./address.txt) contains one complete, lowercase Ethereum address per line.
- [`snapshot.json`](./snapshot.json) records the source, generation time, row count, and SHA-256 digest.
- The publisher fails closed if any page is incomplete, any address is malformed,
  or the combined snapshot contains duplicates. A failed refresh never replaces the
  last validated snapshot.

This is a point-in-time ranking from a third-party explorer. It is not an
authoritative ledger dataset and should not be treated as financial advice.

## Refresh locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The scheduled GitHub Actions job refreshes the snapshot every Sunday. Pull
requests run parser tests without publishing data.

## Validate

```bash
python -m unittest discover -s tests -v
```
