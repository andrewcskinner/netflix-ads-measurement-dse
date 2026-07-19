"""DuckDB access layer.

The warehouse is built once per container from the seeded generator (first
boot takes ~20s, then it's cached on disk). Query text lives in sql/*.sql so
the analytical SQL is a first-class, reviewable part of the repo — every page
exposes the query it ran.
"""

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT / "data" / "netflix_ads.duckdb")
SQL_DIR = ROOT / "sql"


def ensure_built() -> None:
    if os.path.exists(DB_PATH):
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    from src.datagen.generate import build
    with st.status("First boot: generating the synthetic warehouse (~1M placements)…",
                   expanded=True) as status:
        build(DB_PATH, progress=st.write)
        status.update(label="Warehouse ready", state="complete", expanded=False)


@st.cache_resource
def connection() -> duckdb.DuckDBPyConnection:
    ensure_built()
    return duckdb.connect(DB_PATH, read_only=True)


def sql_text(name: str) -> str:
    return (SQL_DIR / f"{name}.sql").read_text()


@st.cache_data(show_spinner=False)
def run_sql(name: str, params: tuple = ()) -> pd.DataFrame:
    """Run a named query from sql/ with optional positional parameters."""
    return connection().execute(sql_text(name), list(params)).df()


@st.cache_data(show_spinner=False)
def query(q: str, params: tuple = ()) -> pd.DataFrame:
    """Run ad-hoc SQL (used for small lookups; showcase queries live in sql/)."""
    return connection().execute(q, list(params)).df()


def show_sql(name: str, label: str = "View the SQL behind this analysis"):
    with st.expander(f"⌗ {label}"):
        st.code(sql_text(name), language="sql")
