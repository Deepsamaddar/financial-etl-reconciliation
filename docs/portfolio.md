# Deep Samaddar — Project contribution and interview guide

## How to describe this project

This is a portfolio extension of an existing MIT-licensed ETL project, developed
with AI assistance. Keep the upstream credit and describe the changes you have
reviewed, run, and can explain. Do not describe the inherited project as built
entirely from scratch or claim employment, customer use, or a live AWS deployment.

## Contribution scope in this edition

- Added cross-chunk business-key deduplication and missing/blank key controls.
- Replaced float-based reconciliation decisions with decimal comparisons.
- Added explicit bank-feed validation and one-to-one join protection.
- Fixed empty-reset behaviour that could retain stale warehouse rows.
- Added regression tests and reproducible JSON/HTML reporting.
- Corrected unsupported scalability/deployment claims and documented tradeoffs.

The baseline already supplied the generator, stage structure, SQL examples,
YAML mapping, local audit trail, Lambda mock, and initial unit tests.

## Suggested résumé wording after completing the walkthrough

**Financial ETL & Reconciliation | Python, pandas, SQLAlchemy, PyTest**

- Extended an open-source financial ETL pipeline with cross-chunk duplicate
  detection, decimal-based reconciliation, and regression coverage for malformed
  feeds and stale-data resets.
- Validated a 50,000-record synthetic-data workflow and generated reproducible
  JSON/HTML reports covering accepted records, quarantines, and reconciliation
  exceptions.

These are personal-project statements, not production experience claims.
Only use the wording after reviewing the changes and reproducing the demo.

## Five-minute walkthrough

1. Explain the business problem: malformed feeds and unmatched ledger/bank records.
2. Show the README data flow and distinguish inherited components from extensions.
3. Run the tests and explain one penny-boundary or cross-chunk duplicate test.
4. Generate 50,000 rows, run the pipeline, and open the report.
5. Explain why rejected source records can appear as missing-from-ledger breaks.
6. Discuss memory growth, non-idempotent appends, and the production roadmap.

## Questions to practise

**Why not compare money with floats?** Binary representations can make a difference
of exactly one penny exceed the tolerance; decimal comparisons avoid that boundary
error. Display/storage conversion happens after classification.

**Why did chunking break duplicate detection?** Per-frame `duplicated()` cannot see
IDs in previous frames. A run-wide seen-ID set makes the result chunk-independent,
at the cost of memory proportional to unique IDs.

**What happens when a rerun has no rejects?** Replacement must still create/clear
the quarantine table. Skipping an empty write would retain earlier rejects.

**Is this production-ready?** No. Discuss transactional staging, replay protection,
currency validation, memory constraints, tested database backends, and safe Lambda
deployment as concrete next steps.
