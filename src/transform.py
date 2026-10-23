"""Transform stage: source-to-target mapping and standardisation.

Renames and retypes raw source columns into the curated warehouse schema
defined in ``mapping/source_to_target.yaml``. Cleaning is deterministic and
non-destructive: rows that cannot be coerced are flagged rather than
silently dropped, so the data-quality stage can quarantine them with a
reason code.
"""
from __future__ import annotations

from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

import pandas as pd
import yaml

from .config import ROOT, settings

MAPPING_PATH = ROOT / "mapping" / "source_to_target.yaml"


def load_mapping(path: Path | None = None) -> dict:
    with open(path or MAPPING_PATH) as fh:
        return yaml.safe_load(fh)


def apply_mapping(df: pd.DataFrame, mapping: dict | None = None) -> pd.DataFrame:
    """Rename source columns to target names per the mapping spec."""
    mapping = mapping or load_mapping()
    missing = {c["source"] for c in mapping["columns"]} - set(df.columns)
    if missing:
        raise ValueError(f"Source is missing required columns: {sorted(missing)}")
    rename = {c["source"]: c["target"] for c in mapping["columns"]}
    out = df.rename(columns=rename)
    keep = [c["target"] for c in mapping["columns"]]
    return out[[c for c in keep if c in out.columns]]


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types and normalise values without dropping rows."""
    out = df.copy()
    def minor_units(value):
        try:
            amount = Decimal(str(value))
            if not amount.is_finite():
                return pd.NA
            minor = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
            return minor if -(2**63) <= minor < 2**63 else pd.NA
        except (InvalidOperation, ValueError, OverflowError):
            return pd.NA
    out["amount_minor"] = pd.array(out["amount"].map(minor_units), dtype="Int64")
    for column in ("transaction_id", "account_id"):
        out[column] = out[column].astype("string").str.strip().replace("", pd.NA)
    out["posted_at"] = pd.to_datetime(out["posted_at"], errors="coerce")
    out["currency_code"] = out["currency_code"].str.upper().str.strip()
    out["merchant_name"] = out["merchant_name"].str.strip().str.title()
    out["status"] = out["status"].str.upper().str.strip()
    return out


def transform(df: pd.DataFrame, mapping: dict | None = None) -> pd.DataFrame:
    return standardise(apply_mapping(df, mapping))
