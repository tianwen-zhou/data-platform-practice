"""Land raw transaction files into the local "lake", one partition per business date.

Mirrors what an ingestion job does before dbt runs:
- source data arrives as a JSON lines extract from an upstream system
- it is written unchanged to lake/raw/transactions/dt=YYYY-MM-DD/
- re-running for the same date replaces that partition (idempotent), never appends a duplicate

In AWS the lake would be an S3 bucket; here it is a local folder so the whole flow runs offline.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

LAKE_ROOT = Path(__file__).resolve().parent.parent / "lake"
ACCOUNTS = ["ACC-001", "ACC-002", "ACC-003", "ACC-004"]
CHANNELS = ["card", "eftpos", "online", "atm"]


def generate_transactions(business_date: date, count: int, seed: int | None = None) -> list[dict]:
    """Fake upstream extract. Includes one duplicate row on purpose, as real extracts do."""
    rng = random.Random(seed if seed is not None else business_date.toordinal())
    rows = []
    for i in range(count):
        ts = datetime.combine(business_date, datetime.min.time()) + timedelta(seconds=rng.randint(0, 86_399))
        rows.append(
            {
                "transaction_id": f"{business_date:%Y%m%d}-{i:05d}",
                "account_id": rng.choice(ACCOUNTS),
                "amount_cents": rng.choice([-1, 1]) * rng.randint(100, 50_000),
                "channel": rng.choice(CHANNELS),
                "created_at": ts.isoformat(),
            }
        )
    if rows:
        rows.append(dict(rows[0]))  # upstream sent the same transaction twice
    return rows


def partition_path(business_date: date, lake_root: Path = LAKE_ROOT) -> Path:
    return lake_root / "raw" / "transactions" / f"dt={business_date:%Y-%m-%d}"


def land_partition(rows: list[dict], business_date: date, lake_root: Path = LAKE_ROOT) -> Path:
    """Write the partition atomically: build in a temp folder, then swap it in."""
    target = partition_path(business_date, lake_root)
    tmp = target.with_name(target.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with (tmp / "part-000.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    if target.exists():
        shutil.rmtree(target)
    tmp.rename(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="business date, YYYY-MM-DD")
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    business_date = date.fromisoformat(args.date)
    path = land_partition(generate_transactions(business_date, args.count), business_date)
    print(f"landed {path}")


if __name__ == "__main__":
    main()
