"""
Shared utilities for all generators.

Key design principles:
  - All monetary values use log-normal (heavy right tail, realistic skew)
  - Dates have seasonality injected (not uniform random)
  - Categorical columns use weighted distributions (80/20 rule)
  - ~3% outlier injection on numeric columns
  - Wide tables get extra sparse columns (60-70% NULL, realistic legacy data)
"""

import hashlib
import random
import string
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from faker import Faker

from config import DATA_END_YEAR, DATA_START_YEAR, FAKER_LOCALE, RANDOM_SEED

rng  = np.random.default_rng(RANDOM_SEED)
fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ── Date helpers ───────────────────────────────────────────────────────────

def date_range_days() -> int:
    """Total days spanned by the generator's date range."""
    return (date(DATA_END_YEAR, 12, 31) - date(DATA_START_YEAR, 1, 1)).days


def seasonal_dates(n: int, peak_months: list[int] | None = None) -> pd.Series:
    """
    Generate n dates with seasonal bias.
    peak_months: list of months (1-12) with higher probability.
    Default peaks: Jan (renewals), Jul (mid-year), Oct-Dec (year-end).
    """
    if peak_months is None:
        peak_months = [1, 7, 10, 11, 12]

    start = date(DATA_START_YEAR, 1, 1)
    total_days = date_range_days()

    # Build day weights with seasonal boost
    day_indices = np.arange(total_days)
    weights = np.ones(total_days, dtype=float)
    for i, d in enumerate(start + timedelta(days=int(j)) for j in day_indices):
        if d.month in peak_months:
            weights[i] *= 2.5
        # Weekend slight dip (business data)
        if d.weekday() >= 5:
            weights[i] *= 0.6

    weights /= weights.sum()
    chosen = rng.choice(day_indices, size=n, p=weights)
    return pd.Series([start + timedelta(days=int(d)) for d in chosen])


def random_dates(n: int, start_year: int = DATA_START_YEAR, end_year: int = DATA_END_YEAR) -> pd.Series:
    """n uniformly random dates within [start_year, end_year] — no
    seasonality (see seasonal_dates() for that)."""
    start = date(start_year, 1, 1)
    end   = date(end_year, 12, 31)
    delta = (end - start).days
    return pd.Series([start + timedelta(days=int(d)) for d in rng.integers(0, delta, n)])


def future_dates(base: pd.Series, min_days: int = 30, max_days: int = 730) -> pd.Series:
    """Generate dates after a base date (e.g. policy expiry after start)."""
    deltas = rng.integers(min_days, max_days, len(base))
    return pd.Series([
        b + timedelta(days=int(d)) if isinstance(b, date) else None
        for b, d in zip(base, deltas)
    ])


# ── Numeric distributions ──────────────────────────────────────────────────

def lognormal(n: int, mean: float, sigma: float, outlier_rate: float = 0.03) -> np.ndarray:
    """
    Log-normal with outlier injection.
    Outliers are 5-20x the mean (right tail spikes).
    """
    values = rng.lognormal(mean=np.log(mean), sigma=sigma, size=n)
    # Inject outliers
    n_outliers = max(1, int(n * outlier_rate))
    outlier_idx = rng.choice(n, size=n_outliers, replace=False)
    values[outlier_idx] *= rng.uniform(5, 20, n_outliers)
    return np.round(values, 2)


def clipped_normal(n: int, mean: float, std: float, low: float, high: float) -> np.ndarray:
    """n normally-distributed values, clipped to [low, high]."""
    values = rng.normal(mean, std, n)
    return np.clip(np.round(values, 2), low, high)


def integer_counts(n: int, low: int, high: int, skew: str = "low") -> np.ndarray:
    """Skewed integer counts. skew='low' means most values cluster near low end."""
    if skew == "low":
        return rng.integers(low, high, n) ** 1  # mild, use geometric below
    raw = rng.geometric(p=0.3, size=n) + low - 1
    return np.clip(raw, low, high).astype(int)


# ── Categorical helpers ────────────────────────────────────────────────────

def weighted_choice(options: list, weights: list[float], n: int) -> np.ndarray:
    """Weighted categorical draw. Weights need not sum to 1."""
    w = np.array(weights, dtype=float)
    w /= w.sum()
    return rng.choice(options, size=n, p=w)


def imbalanced_categories(categories: list[str], n: int, top_share: float = 0.8) -> np.ndarray:
    """
    80/20 rule: top ~20% of categories get top_share of rows.
    """
    k = max(1, len(categories) // 5)
    top    = categories[:k]
    bottom = categories[k:]
    w_top    = [top_share / k] * k
    w_bottom = [(1 - top_share) / max(len(bottom), 1)] * len(bottom)
    return weighted_choice(categories, w_top + w_bottom, n)


US_STATES = [
    "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
    "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT",
]

TOP_CITIES = [
    "Los Angeles", "Houston", "Chicago", "Phoenix", "Philadelphia",
    "San Antonio", "San Diego", "Dallas", "San Jose", "Austin",
    "Jacksonville", "Fort Worth", "Columbus", "Charlotte", "Indianapolis",
    "San Francisco", "Seattle", "Denver", "Nashville", "Oklahoma City",
]


def state_series(n: int) -> np.ndarray:
    """n US state codes, imbalanced toward the more populous ones."""
    return imbalanced_categories(US_STATES, n, top_share=0.75)


def city_series(n: int) -> np.ndarray:
    """n US city names, imbalanced toward the more populous ones."""
    return imbalanced_categories(TOP_CITIES, n, top_share=0.80)


# ── Null injection ─────────────────────────────────────────────────────────

def inject_nulls(series: pd.Series, null_rate: float) -> pd.Series:
    """Randomly set null_rate fraction of values to None."""
    mask = rng.random(len(series)) < null_rate
    result = series.copy().astype(object)
    result[mask] = None
    return result


# ── Wide table extra columns ───────────────────────────────────────────────

def generate_wide_columns(n_rows: int, n_extra: int, table_prefix: str) -> dict[str, pd.Series]:
    """Build all wide columns up-front as a dict, then concat once in the caller."""
    """
    Generate n_extra columns for a wide table.
    Mix of: numeric flags, score fields, legacy text, sparse booleans.
    Most are 60-70% NULL to mimic real legacy wide tables.
    """
    cols: dict[str, pd.Series] = {}

    col_types = ["score", "flag", "amount", "text", "rate", "count", "bool"]
    type_weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.05, 0.05]

    for i in range(n_extra):
        col_type = weighted_choice(col_types, type_weights, 1)[0]
        col_name = f"{table_prefix}_{col_type}_{i+1:03d}"
        null_rate = rng.uniform(0.55, 0.75)  # 55-75% NULL

        if col_type == "score":
            base = pd.Series(clipped_normal(n_rows, 500, 150, 0, 1000))
        elif col_type == "flag":
            base = pd.Series(weighted_choice(["Y", "N", "P", "U"], [0.3, 0.5, 0.1, 0.1], n_rows))
        elif col_type == "amount":
            base = pd.Series(lognormal(n_rows, mean=5000, sigma=1.2))
        elif col_type == "text":
            base = pd.Series([fake.bs() for _ in range(n_rows)])
        elif col_type == "rate":
            base = pd.Series(np.round(rng.uniform(0, 1, n_rows), 4))
        elif col_type == "count":
            base = pd.Series(rng.integers(0, 100, n_rows))
        else:  # bool
            base = pd.Series(rng.choice([True, False], n_rows, p=[0.3, 0.7]))

        cols[col_name] = inject_nulls(base, null_rate)

    return cols


# ── ID helpers ─────────────────────────────────────────────────────────────

def sequential_ids(n: int, prefix: str = "") -> pd.Series:
    """1..n as either zero-padded prefixed strings or plain integers."""
    if prefix:
        return pd.Series([f"{prefix}{i+1:08d}" for i in range(n)])
    return pd.Series(range(1, n + 1))


def foreign_keys(n: int, ref_max: int, null_rate: float = 0.0) -> pd.Series:
    """Draw n foreign key values from 1..ref_max, with optional nulls."""
    fk = pd.Series(rng.integers(1, ref_max + 1, n))
    if null_rate > 0:
        fk = inject_nulls(fk, null_rate)
    return fk


# ── Misc ───────────────────────────────────────────────────────────────────

def random_codes(n: int, length: int = 8) -> pd.Series:
    """n random alphanumeric codes of the given length."""
    chars = string.ascii_uppercase + string.digits
    return pd.Series(["".join(random.choices(chars, k=length)) for _ in range(n)])


def save_parquet(df: pd.DataFrame, path) -> None:
    """Writes a DataFrame to `path` as snappy-compressed parquet."""
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")


def load_parquet(path) -> pd.DataFrame:
    """Reads a parquet file back into a DataFrame."""
    return pd.read_parquet(path, engine="pyarrow")
