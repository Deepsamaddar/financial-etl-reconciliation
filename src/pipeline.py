"""Pipeline orchestrator.

Chains the stages end to end: extract source chunks -> transform (map to
target schema) -> data-quality gate -> load clean + quarantine ->
reconcile against the bank feed -> persist breaks. Every stage writes to
the audit trail so the whole run is traceable.

Extract/load are chunked; reconciliation retains the ledger and bank feed
in memory. This demo is not a constant-memory or production Lambda system.

Usage:
    python -m src.pipeline --source data/source --reset
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import data_quality, load, reconciliation, transform
from .audit import AuditTrail
from .config import settings


def run(source_dir: str | Path, reset: bool = False,
        chunk_size: int | None = None) -> dict:
    source_dir = Path(source_dir)
    chunk_size = settings.chunk_size if chunk_size is None else chunk_size
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    audit = AuditTrail()
    engine = load.get_engine()
    mapping = transform.load_mapping()

    if_exists = "replace" if reset else "append"
    audit.record("start", "pipeline run started", source=str(source_dir))

    rows_in = rows_clean = rows_quarantined = 0
    curated_frames: list[pd.DataFrame] = []
    seen_keys: set = set()

    reader = pd.read_csv(source_dir / "transactions.csv",
                         dtype=str, chunksize=chunk_size)
    for i, chunk in enumerate(reader):
        tf = transform.transform(chunk, mapping)
        dq = data_quality.run_checks(tf, mapping, seen_keys)
        load.load_curated(dq.clean, engine, if_exists if i == 0 else "append")
        load.load_quarantine(dq.quarantine, engine, if_exists if i == 0 else "append")
        curated_frames.append(dq.clean[["transaction_id", "amount"]].assign(
            amount=pd.to_numeric(dq.clean["amount"], errors="coerce")))
        rows_in += dq.total
        rows_clean += len(dq.clean)
        rows_quarantined += len(dq.quarantine)
        audit.record("dq", f"chunk {i} checked", **dq.report())

    audit.record("load", "curated + quarantine loaded",
                 rows_in=rows_in, rows_clean=rows_clean,
                 rows_quarantined=rows_quarantined)

    # Reconciliation against the bank feed.
    ledger = pd.concat(curated_frames, ignore_index=True) if curated_frames else pd.DataFrame(
        columns=["transaction_id", "amount"])
    bank = pd.read_csv(source_dir / "bank_statement.csv", dtype=str)
    recon = reconciliation.reconcile(ledger, bank)
    break_frames = [frame.assign(break_type=kind) for kind, frame in (
        ("amount_break", recon.amount_break), ("missing_bank", recon.missing_bank),
        ("missing_ledger", recon.missing_ledger)) if not frame.empty]
    breaks = (pd.concat(break_frames, ignore_index=True) if break_frames else
              recon.amount_break.assign(break_type=pd.Series(dtype="str")))
    load.load_recon_breaks(breaks, engine, if_exists)
    audit.record("reconcile", "reconciliation complete", **recon.summary())

    result = {
        "run_id": audit.run_id,
        "rows_in": rows_in,
        "rows_clean": rows_clean,
        "rows_quarantined": rows_quarantined,
        "reconciliation": recon.summary(),
    }
    audit.record("done", "pipeline run finished", **result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Run the ETL & reconciliation pipeline")
    p.add_argument("--source", type=Path, default=Path("data/source"))
    p.add_argument("--reset", action="store_true", help="replace target tables")
    p.add_argument("--chunk-size", type=int, default=None)
    p.add_argument("--report-dir", type=Path, help="write JSON summary and standalone HTML report")
    args = p.parse_args()
    result = run(args.source, reset=args.reset, chunk_size=args.chunk_size)
    if args.report_dir:
        from .reporting import write_report
        write_report(result, args.report_dir)
    print("Pipeline complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
