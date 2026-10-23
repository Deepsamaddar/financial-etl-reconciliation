"""Reconciliation engine.

Matches the curated ledger against an external bank statement feed and
classifies every transaction into one of four buckets:

    matched        present in both, amounts agree within tolerance
    amount_break   present in both, amounts differ beyond tolerance
    missing_bank   in the ledger but absent from the bank feed
    missing_ledger in the bank feed but absent from the ledger

The tolerance absorbs currency rounding so genuine penny-level breaks are
surfaced without drowning in noise.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd

from .config import settings


@dataclass
class ReconResult:
    matched: pd.DataFrame
    amount_break: pd.DataFrame
    missing_bank: pd.DataFrame
    missing_ledger: pd.DataFrame

    def summary(self) -> dict:
        return {
            "matched": len(self.matched),
            "amount_break": len(self.amount_break),
            "missing_bank": len(self.missing_bank),
            "missing_ledger": len(self.missing_ledger),
        }

    @property
    def break_count(self) -> int:
        return len(self.amount_break) + len(self.missing_bank) + len(self.missing_ledger)


def reconcile(ledger: pd.DataFrame, bank: pd.DataFrame,
              tolerance: float | None = None) -> ReconResult:
    tol = Decimal(str(settings.reconciliation_tolerance if tolerance is None else tolerance))
    if not tol.is_finite() or tol < 0:
        raise ValueError("tolerance must be finite and non-negative")

    def prepare(frame, key, side):
        required = {key, "amount"}
        if not required.issubset(frame.columns):
            raise ValueError(f"{side}: missing required columns {sorted(required - set(frame.columns))}")
        out = frame[[key, "amount"]].copy().rename(columns={key: "transaction_id"})
        ids = out["transaction_id"].astype("string").str.strip()
        if ids.isna().any() or ids.eq("").any() or ids.duplicated().any():
            raise ValueError(f"{side}: transaction IDs must be present and unique")
        out["transaction_id"] = ids
        def money(value):
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValueError(f"{side}: amounts must be finite numbers") from None
            if not number.is_finite():
                raise ValueError(f"{side}: amounts must be finite numbers")
            return number
        out[f"amount_{side}"] = out.pop("amount").map(money)
        return out

    led = prepare(ledger, "transaction_id", "ledger")
    bnk = prepare(bank, "txn_id", "bank")
    merged = led.merge(bnk, on="transaction_id", how="outer", indicator=True,
                       validate="one_to_one")
    merged["delta"] = [abs(a - b) if flag == "both" else None
                       for a, b, flag in zip(merged["amount_ledger"],
                                             merged["amount_bank"], merged["_merge"])]

    missing_bank = merged[merged["_merge"] == "left_only"].copy()
    missing_ledger = merged[merged["_merge"] == "right_only"].copy()
    both = merged[merged["_merge"] == "both"]

    matched = both[both["delta"] <= tol].copy()
    amount_break = both[both["delta"] > tol].copy()

    # SQL/report values use floats; classification above uses exact decimal arithmetic.
    for frame in (matched, amount_break, missing_bank, missing_ledger):
        for column in ("amount_ledger", "amount_bank", "delta"):
            frame[column] = frame[column].map(lambda x: float(x) if pd.notna(x) else None)
    cols = ["transaction_id", "amount_ledger", "amount_bank", "delta"]
    return ReconResult(
        matched=matched[cols].reset_index(drop=True),
        amount_break=amount_break[cols].reset_index(drop=True),
        missing_bank=missing_bank[cols].reset_index(drop=True),
        missing_ledger=missing_ledger[cols].reset_index(drop=True),
    )
