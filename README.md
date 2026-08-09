# Ethereum top-address snapshot

A weekly, validated snapshot of the top 10,000 Ethereum accounts by ETH balance,
as indexed by [Blockscout](https://eth.blockscout.com/).

## Data

- [`address.txt`](./address.txt) contains one complete, lowercase Ethereum address per line.
- [`snapshot.json`](./snapshot.json) records the API source, generation time, row count, and SHA-256 digest.
- The publisher fails closed if the API returns malformed addresses or balances
  or broken pagination. It removes cross-page duplicates and locally sorts the
  returned balance values before atomically replacing the previous snapshot.

This is collected from a live, paginated third-party explorer index. Balances
can change while pages are fetched, so it is not an atomic chain-state view or
an authoritative ledger dataset and should not be treated as financial advice.

## Refresh locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The scheduled GitHub Actions job refreshes the snapshot every Sunday. Pull
requests run pagination and validation tests without publishing data.

## Validate

```bash
python -m unittest discover -s tests -v
```
