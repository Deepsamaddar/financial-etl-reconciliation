# Deep Samaddar — Validation evidence

Validated locally on 23 October 2026 using Python 3.12.14, pandas 3.1.0,
SQLAlchemy 2.1.6, and SQLite. Exact environment versions are recorded in
`requirements-python312.txt` (Python 3.12 environment snapshot, not a
cross-version lockfile).

## Automated suite

`python -m pytest -q -o addopts=''` → **44 passed**.

Coverage includes the inherited unit/mocked-S3 tests and added regression checks
for penny thresholds, nonfinite bank amounts, invalid tolerances, duplicate joins,
chunk-spanning duplicates, empty replacement, empty full runs, missing source
headers, blank IDs, out-of-range amounts, decimal minor units, report escaping, missing reconciliation keys, invalid chunk sizes, all-rejected
source feeds, and large decimal amounts carried through the complete pipeline.

## Synthetic demo

```bash
python -m src.generate_data --rows 50000 --out data/source
python -m src.pipeline --source data/source --reset --chunk-size 7000 --report-dir examples/demo
```

| Metric | Observed |
|---|---:|
| Input records | 50,000 |
| Accepted | 48,512 |
| Quarantined | 1,488 |
| Matched | 48,029 |
| Amount differences | 1 |
| Missing from bank | 482 |
| Missing from accepted ledger | 1,488 |

Control totals: 48,512 + 1,488 = 50,000 source records;
48,029 + 1 + 482 = 48,512 accepted ledger records.

These counts are from synthetic data with seed 42, not customer data. The generator
intentionally damages some source rows while keeping the independent bank feed
valid. Runtime is not presented as a benchmark. The run-specific ID appears in
`examples/demo/summary.json` and the HTML report.

## Scope

Local tests verify SQLite and mocked AWS behaviour. Live AWS, PostgreSQL, MSSQL,
concurrent events, restart recovery, and 10M-row performance were not validated.
GitHub Actions results should be checked separately on this fork.

## Follow-up cross-check

The 50,000-row feed was rerun at chunk sizes 4,096, 7,000, and 50,000.
All run summaries agreed after excluding the unique run ID. Database checks
confirmed accepted-row totals, unique transaction IDs, quarantine totals, and
stored exception counts.

A new regression exposed premature float conversion in the pipeline for
`900719925474099.95`. The identical ledger/bank amounts previously produced
a false amount break. Preserving decimal text until reconciliation fixed it.

The name shown on the README and generated report is Deep Samaddar. The original
MIT license remains unchanged, and the source-baseline link is retained.
