"""Regression coverage for observed failure modes in the original project."""
import json

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from src import data_quality, load, transform
from src.pipeline import run
from src.reconciliation import reconcile
from src.reporting import write_report


def frames(amount='100.00', bank_amount='100.01'):
    return (pd.DataFrame({'transaction_id': ['001'], 'amount': [amount]}),
            pd.DataFrame({'txn_id': ['001'], 'amount': [bank_amount]}))


def test_exact_penny_boundary():
    assert reconcile(*frames(), tolerance=0.01).summary()['matched'] == 1
    assert reconcile(*frames(), tolerance=0.009).summary()['amount_break'] == 1


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', 'bad', None])
def test_invalid_amounts_fail_loudly(value):
    with pytest.raises(ValueError, match='finite numbers'):
        reconcile(*frames(bank_amount=value))


@pytest.mark.parametrize('tolerance', [-1, float('inf'), float('nan')])
def test_invalid_tolerance(tolerance):
    with pytest.raises(ValueError, match='tolerance'):
        reconcile(*frames(), tolerance=tolerance)


@pytest.mark.parametrize('side', [0, 1])
def test_duplicate_ids_do_not_multiply_join_rows(side):
    feeds = list(frames())
    feeds[side] = pd.concat([feeds[side], feeds[side]], ignore_index=True)
    with pytest.raises(ValueError, match='unique'):
        reconcile(*feeds)


def test_duplicate_across_chunks(raw_frame):
    seen = set()
    a = data_quality.run_checks(transform.transform(raw_frame.iloc[:1]), seen_keys=seen)
    b = data_quality.run_checks(transform.transform(raw_frame.iloc[4:]), seen_keys=seen)
    assert len(a.clean) == 1
    assert b.quarantine['dq_reason'].tolist() == ['duplicate_transaction_id']


def test_empty_replace_clears_old_rows():
    engine = create_engine('sqlite://')
    frame = pd.DataFrame({'transaction_id': ['old'], 'amount': [1]})
    load.load_curated(frame, engine, 'replace')
    load.load_curated(frame.iloc[:0], engine, 'replace')
    with engine.connect() as connection:
        assert connection.execute(text('select count(*) from fact_transaction')).scalar() == 0


def test_pipeline_chunk_independence_and_reset(raw_frame, tmp_path, monkeypatch):
    monkeypatch.setenv('ETL_TARGET_DSN', f'sqlite:///{tmp_path / "warehouse.db"}')
    source = tmp_path / 'source'
    source.mkdir()
    raw_frame.to_csv(source / 'transactions.csv', index=False)
    pd.DataFrame({'txn_id': ['TXN000000000001', 'TXN000000000002'],
                  'amount': ['12.50', '-8.00']}).to_csv(source / 'bank_statement.csv', index=False)
    small = run(source, reset=True, chunk_size=1)
    large = run(source, reset=True, chunk_size=100)
    assert {k: v for k, v in small.items() if k != 'run_id'} == {
        k: v for k, v in large.items() if k != 'run_id'}
    assert small['rows_clean'] == 2
    assert small['rows_in'] == small['rows_clean'] + small['rows_quarantined']
    raw_frame.iloc[:0].to_csv(source / 'transactions.csv', index=False)
    pd.DataFrame(columns=['txn_id', 'amount']).to_csv(source / 'bank_statement.csv', index=False)
    empty = run(source, reset=True, chunk_size=10)
    assert empty['rows_in'] == 0
    with load.get_engine().connect() as connection:
        for table in ('fact_transaction', 'dq_quarantine', 'recon_breaks'):
            assert connection.execute(text(f'select count(*) from {table}')).scalar() == 0


def test_report_matches_summary_and_escapes_text(tmp_path):
    result = {'run_id': '<script>bad()</script>', 'rows_in': 10, 'rows_clean': 8,
              'rows_quarantined': 2, 'reconciliation': {'matched': 7, 'amount_break': 1,
                                                     'missing_bank': 0, 'missing_ledger': 2}}
    report = write_report(result, tmp_path)
    assert json.loads((tmp_path / 'summary.json').read_text()) == result
    assert '80.00%' in report.read_text()
    assert '<script>' not in report.read_text()


@pytest.mark.parametrize('amount', ['Infinity', '-Infinity', 'NaN', 'bad', '1e99'])
def test_nonfinite_or_out_of_range_source_amount_quarantined(raw_frame, amount):
    source = raw_frame.iloc[:1].copy()
    source['amount'] = amount
    checked = data_quality.run_checks(transform.transform(source))
    assert len(checked.clean) == 0
    assert checked.quarantine['dq_reason'].tolist() == ['amount_not_numeric']


def test_missing_source_header_has_actionable_error(raw_frame):
    with pytest.raises(ValueError, match='account_id'):
        transform.transform(raw_frame.drop(columns='account_id'))


def test_blank_key_is_quarantined(raw_frame):
    source = raw_frame.iloc[:1].copy()
    source['txn_id'] = '   '
    checked = data_quality.run_checks(transform.transform(source))
    assert checked.quarantine['dq_reason'].tolist() == ['null_transaction_id']


def test_decimal_minor_units(raw_frame):
    source = raw_frame.iloc[:1].copy()
    source['amount'] = '1.015'
    assert transform.transform(source)['amount_minor'].tolist() == [102]
