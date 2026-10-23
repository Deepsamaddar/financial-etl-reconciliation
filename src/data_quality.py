"""Data-quality controls.

Applies a battery of rule checks to the standardised frame and splits it
into a clean set (safe to load) and a quarantine set (each row tagged with
a ``dq_reason``). Rules are driven by the same mapping spec used by the
transform stage, so schema and quality stay in lock-step.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .transform import load_mapping


@dataclass
class DQResult:
    clean: pd.DataFrame
    quarantine: pd.DataFrame

    @property
    def total(self) -> int:
        return len(self.clean) + len(self.quarantine)

    @property
    def pass_rate(self) -> float:
        return 0.0 if self.total == 0 else len(self.clean) / self.total

    def report(self) -> dict:
        reasons = (
            self.quarantine["dq_reason"].value_counts().to_dict()
            if not self.quarantine.empty
            else {}
        )
        return {
            "rows_in": self.total,
            "rows_clean": len(self.clean),
            "rows_quarantined": len(self.quarantine),
            "pass_rate": round(self.pass_rate, 4),
            "reasons": reasons,
        }


def run_checks(df: pd.DataFrame, mapping: dict | None = None,
               seen_keys: set | None = None) -> DQResult:
    mapping = mapping or load_mapping()
    df = df.copy()
    reason = pd.Series(pd.NA, index=df.index, dtype="object")

    def flag(mask: pd.Series, label: str) -> None:
        # first failing rule wins, keeping the reason deterministic
        newly = mask & reason.isna()
        reason.loc[newly] = label

    # not-null constraints
    for col in [c for c in mapping["columns"] if c.get("nullable") is False]:
        t = col["target"]
        if t in df.columns:
            flag(df[t].isna(), f"null_{t}")

    # amount must be numeric and present
    if "amount_minor" in df.columns:
        flag(df["amount_minor"].isna(), "amount_not_numeric")

    # timestamp must parse
    if "posted_at" in df.columns:
        flag(df["posted_at"].isna(), "bad_timestamp")

    # domain / referential checks
    for col in [c for c in mapping["columns"] if "domain" in c]:
        t = col["target"]
        if t in df.columns:
            flag(~df[t].isin(col["domain"]) & df[t].notna(), f"invalid_{t}")

    # uniqueness on the business key
    key = next((c["target"] for c in mapping["columns"] if c.get("key")), None)
    if key and key in df.columns:
        flag(df[key].duplicated(keep="first") |
             df[key].isin(seen_keys if seen_keys is not None else set()), f"duplicate_{key}")
        if seen_keys is not None:
            seen_keys.update(df[key].dropna().tolist())

    quarantine = df[reason.notna()].assign(dq_reason=reason[reason.notna()])
    clean = df[reason.isna()].drop(columns=[c for c in ["dq_reason"] if c in df.columns])
    return DQResult(clean=clean, quarantine=quarantine)
