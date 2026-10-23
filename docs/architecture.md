# Architecture and design decisions

## Processing contract

Source CSV → mapping/type coercion → quality gate → clean and quarantine tables
→ current-run reconciliation → exception table. Each completed stage emits a
local JSONL event keyed by run ID. The report renders the returned summary.

Required source headers come from `mapping/source_to_target.yaml`. Blank IDs
are normalised to null. Amount minor units use decimal arithmetic with half-even
rounding and a signed 64-bit bound. Invalid/nonfinite amounts are quarantined.

## Duplicate policy

The first occurrence of an ID reserves it for the run, even if that row is
quarantined for another reason. Later occurrences are quarantined. This avoids
quietly choosing a replacement transaction. The same policy applies within a
chunk and across chunks. A run-local set tracks observed IDs; it does not inspect
previous runs in the warehouse. Replay-safe loading remains future work.

The bank feed must have unique, nonblank IDs and finite amounts. Reconciliation
fails clearly when that contract is violated; the merge also enforces one-to-one
cardinality. Operators must correct the feed before retrying.

## Monetary comparisons

`Decimal(str(value))` avoids binary floating-point errors at tolerance boundaries.
The pipeline preserves source amount text until reconciliation, including amounts
large enough to lose cents in binary floats. The comparison uses the exact supplied
decimal amount; report and SQL values are
converted to float only after classification. Minor units are a separate rounded
warehouse field. This supports the demo’s two-decimal currencies, not arbitrary
currency precision or FX conversion. Currency equality is assumed, not checked.

## Resource and storage limits

Extraction and writes are chunked, but reconciliation concatenates the accepted
ledger and reads the whole bank feed. Both this merge and the ID set grow with
input size. There is no verified constant-memory or 10M-row claim. A production
version should use indexed database staging, run-scoped keys, database-side
anti-joins, and measured memory/time budgets.

`--reset` recreates tables even for empty outputs, preventing stale data. Pandas
replacement can discard database constraints, so it belongs to a disposable demo
warehouse. Append mode is not idempotent. There is no atomic transaction around
the full run; a late failure may leave partially loaded tables. Reconciliation
covers the current source batch, not all historical rows in the target.

## AWS and database scope

S3/Lambda is a moto-backed integration example. Production deployment needs a
writable runtime data directory, event decoding/filtering, feed-readiness checks,
least-privilege access, durable state, retries, deduplication, and concurrency
controls. The current handler resets its target and is not deployment-ready.
PostgreSQL and MSSQL scripts are reference assets; the verified local path is
SQLite. pandas stages do not run unchanged as distributed Spark operations.

## Next engineering milestones

1. Add run-scoped staging and transactional promotion with replay-safe keys.
2. Reconcile currency as well as identity and amount; quarantine invalid bank rows.
3. Move joins and deduplication into an indexed database and benchmark at scale.
4. Add database-backed integration tests and a safe, packaged Lambda deployment.
5. Add immutable audit storage and operational failure/recovery reporting.
