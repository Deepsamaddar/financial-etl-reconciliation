"""Synthetic source-data generator.

Produces a realistic, messy feed of financial transactions plus a matching
bank statement feed used by the reconciliation engine. Data is written in
chunks so tens of millions of rows can be generated with a flat memory
footprint. A configurable fraction of rows is deliberately corrupted
(nulls, bad currencies, duplicated ids, penny mismatches) so the
data-quality and reconciliation stages have something to catch.

Usage:
    python -m src.generate_data --rows 10000000 --out data/source
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings

MERCHANTS = [
    "Amazon", "Tesco", "Shell", "Uber", "Spotify", "Apple", "Deliveroo",
    "British Gas", "Vodafone", "Netflix", "Sainsburys", "Costa",
]
CHANNELS = ["CARD", "ACH", "WIRE", "DIRECT_DEBIT", "STANDING_ORDER"]
STATUSES = ["POSTED", "PENDING", "SETTLED", "REVERSED"]


def _row(i: int, rng: random.Random, corrupt: bool) -> dict:
    ts = datetime(2024, 1, 1) + timedelta(seconds=rng.randint(0, 60 * 60 * 24 * 365))
    amount = round(rng.uniform(-2500, 5000), 2)
    row = {
        "txn_id": f"TXN{i:012d}",
        "account_id": f"AC{rng.randint(1, 250_000):08d}",
        "posted_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "merchant": rng.choice(MERCHANTS),
        "channel": rng.choice(CHANNELS),
        "currency": rng.choices(settings.currencies, weights=[70, 15, 10, 5])[0],
        "amount": amount,
        "status": rng.choice(STATUSES),
    }
    if corrupt:
        kind = rng.random()
        if kind < 0.30:
            row["currency"] = "XXX"          # invalid currency code
        elif kind < 0.55:
            row["amount"] = ""               # missing amount
        elif kind < 0.75:
            row["account_id"] = ""           # missing FK
        elif kind < 0.90:
            row["posted_at"] = "not-a-date"  # unparseable timestamp
        else:
            row["txn_id"] = f"TXN{max(i - 1, 0):012d}"  # duplicate id
    return row


def generate(rows: int, out_dir: Path, corrupt_rate: float = 0.03) -> Path:
    """Write ``rows`` transactions plus a bank feed to ``out_dir``.

    The bank feed mirrors the source but drops a handful of rows and nudges
    a few amounts by a penny, creating genuine breaks to reconcile.
    """
    if rows < 0 or not 0 <= corrupt_rate <= 1:
        raise ValueError("rows must be non-negative and corrupt_rate must be between 0 and 1")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(settings.seed)
    src_path = out_dir / "transactions.csv"
    bank_path = out_dir / "bank_statement.csv"

    fields = list(_row(0, rng, False).keys())
    with src_path.open("w", newline="") as sf, bank_path.open("w", newline="") as bf:
        sw = csv.DictWriter(sf, fieldnames=fields)
        bw = csv.DictWriter(bf, fieldnames=["txn_id", "amount", "currency"])
        sw.writeheader()
        bw.writeheader()
        for i in range(1, rows + 1):
            corrupt = rng.random() < corrupt_rate
            # The independent bank feed retains valid identity and amount even
            # when the source feed is deliberately damaged.
            bank_row = _row(i, rng, False)
            r = _row(i, rng, True) if corrupt else bank_row
            sw.writerow(r)
            # Bank feed: 1% of clean rows go missing, 1% shift by a penny.
            if not corrupt and rng.random() < 0.01:
                continue
            amt = bank_row["amount"]
            if isinstance(amt, float) and rng.random() < 0.01:
                amt = round(amt + 0.01, 2)
            bw.writerow({"txn_id": bank_row["txn_id"], "amount": amt, "currency": bank_row["currency"]})
    return src_path


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic transaction feeds")
    p.add_argument("--rows", type=int, default=settings.default_rows)
    p.add_argument("--out", type=Path, default=Path("data/source"))
    p.add_argument("--corrupt-rate", type=float, default=0.03)
    args = p.parse_args()
    path = generate(args.rows, args.out, args.corrupt_rate)
    print(f"Generated {args.rows:,} rows -> {path}")


if __name__ == "__main__":
    main()
