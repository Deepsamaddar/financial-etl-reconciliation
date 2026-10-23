"""Load stage.

Writes curated rows and quarantined rows to the target warehouse via
SQLAlchemy. The default DSN is a local SQLite file so the demo runs with
no infrastructure; point ``ETL_TARGET_DSN`` at PostgreSQL or MSSQL for a
real deployment (the same code path is used either way).
"""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import settings

CURATED_TABLE = "fact_transaction"
QUARANTINE_TABLE = "dq_quarantine"
RECON_TABLE = "recon_breaks"


def get_engine(dsn: str | None = None) -> Engine:
    # Read the DSN at call time so it can be overridden per-process (env var
    # or explicit argument) without re-importing config.
    dsn = dsn or os.getenv("ETL_TARGET_DSN", settings.target_dsn)
    return create_engine(dsn, future=True)


def _write(df: pd.DataFrame, table: str, engine: Engine, if_exists: str) -> int:
    df.to_sql(table, engine, if_exists=if_exists, index=False)
    return len(df)


def load_curated(df: pd.DataFrame, engine: Engine | None = None,
                 if_exists: str = "append") -> int:
    return _write(df, CURATED_TABLE, engine or get_engine(), if_exists)


def load_quarantine(df: pd.DataFrame, engine: Engine | None = None,
                    if_exists: str = "append") -> int:
    return _write(df, QUARANTINE_TABLE, engine or get_engine(), if_exists)


def load_recon_breaks(df: pd.DataFrame, engine: Engine | None = None,
                      if_exists: str = "append") -> int:
    return _write(df, RECON_TABLE, engine or get_engine(), if_exists)
