import json

from app.discovery.introspect import ColumnInfo
from app.discovery.profiler import ColumnProfile
from app.discovery.signature import column_signature


def _col(**overrides):
    defaults = dict(name="a", data_type="integer", is_pk=False, is_fk=False, fk_table=None, fk_column=None)
    defaults.update(overrides)
    return ColumnInfo(**defaults)


def _profile(**overrides):
    defaults = dict(row_count=100, null_rate=0.1, distinct_count=5)
    defaults.update(overrides)
    return ColumnProfile(**defaults)


def _large_profile(**overrides):
    # Above DISCOVERY_LARGE_TABLE_ROWS (50_000) — profiled via TABLESAMPLE,
    # so stats are expected to vary run-to-run even with unchanged data.
    defaults = dict(row_count=500_000, null_rate=0.1, distinct_count=5)
    defaults.update(overrides)
    return ColumnProfile(**defaults)


def test_signature_is_stable_for_identical_input():
    col, profile = _col(), _profile()
    assert column_signature(col, profile) == column_signature(col, profile)


def test_signature_changes_when_distinct_count_changes():
    col = _col()
    assert column_signature(col, _profile(distinct_count=5)) != column_signature(col, _profile(distinct_count=9))


def test_signature_changes_when_data_type_changes():
    profile = _profile()
    assert column_signature(_col(data_type="integer"), profile) != column_signature(_col(data_type="bigint"), profile)


def test_signature_ignores_float_noise_below_rounding_precision():
    col = _col()
    a = column_signature(col, _profile(mean_value=3.14159))
    b = column_signature(col, _profile(mean_value=3.14160))
    assert a == b


def test_signature_matches_after_a_jsonb_round_trip():
    """The hash computed from a live profile (Decimal-ish/native Python
    values) must equal the hash computed from that same profile after it's
    been written to JSONB and read back (plain str/float/int/list) — this is
    exactly what compares a fresh profiling run against a backfilled
    content_hash. A mismatch here means every column looks "changed" on the
    next real run even when nothing actually changed."""
    col = _col(data_type="numeric")
    from decimal import Decimal
    live_profile = _profile(min_value=Decimal("12.50"), max_value=Decimal("99.90"), mean_value=45.678)

    round_tripped = json.loads(json.dumps(live_profile.model_dump(mode="json")))
    reloaded_profile = ColumnProfile(**round_tripped)

    assert column_signature(col, live_profile) == column_signature(col, reloaded_profile)


def test_signature_for_large_sampled_table_ignores_stat_noise():
    """A table above DISCOVERY_LARGE_TABLE_ROWS is profiled via a random
    2% sample every run — different min/max/distinct/top_values/histogram
    each time even when nothing actually changed. The signature must not
    treat that noise as a real change."""
    col = _col()
    a = _large_profile(distinct_count=100, min_value=1, max_value=999, top_values=[("x", 5)])
    b = _large_profile(distinct_count=140, min_value=7, max_value=950, top_values=[("y", 3)])
    assert column_signature(col, a) == column_signature(col, b)


def test_signature_for_large_sampled_table_still_reacts_to_row_count_change():
    col = _col()
    a = _large_profile(row_count=500_000)
    b = _large_profile(row_count=510_000)
    assert column_signature(col, a) != column_signature(col, b)


def test_signature_for_small_table_still_reacts_to_stat_change():
    col = _col()
    a = _profile(distinct_count=5)
    b = _profile(distinct_count=9)
    assert column_signature(col, a) != column_signature(col, b)


def test_signature_matches_after_a_datetime_jsonb_round_trip():
    """A live datetime.datetime min/max stringifies as '2015-01-01 00:00:00'
    (space-separated) via str(); the same value read back from the profile
    JSONB column is already an ISO string '2015-01-01T00:00:00'
    ('T'-separated — how pydantic's mode="json" serializes it). Naive str()
    normalization made those hash differently forever, so any table with a
    date/datetime column looked "changed" on every single run."""
    import datetime
    col = _col(data_type="timestamp without time zone")
    live_profile = _profile(min_value=datetime.datetime(2015, 1, 1, 0, 0), max_value=datetime.datetime(2024, 12, 30, 0, 0))

    round_tripped = json.loads(json.dumps(live_profile.model_dump(mode="json")))
    reloaded_profile = ColumnProfile(**round_tripped)

    assert column_signature(col, live_profile) == column_signature(col, reloaded_profile)


def test_signature_recomputed_from_stored_profile_matches_stored_hash():
    """The strongest guard against this whole bug class: whatever hash gets
    stored for a profile, recomputing the signature from that *same* profile
    (as read back out of the DB) must reproduce the identical hash. If this
    fails, the stored content_hash can never match a future correct run,
    regardless of whether the underlying data ever changes."""
    import datetime
    col = _col(data_type="date")
    profile = _profile(min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2020, 12, 31), top_values=[("x", 3), ("y", 1)])

    stored_hash = column_signature(col, profile)
    round_tripped = json.loads(json.dumps(profile.model_dump(mode="json")))
    reloaded_profile = ColumnProfile(**round_tripped)
    recomputed_hash = column_signature(col, reloaded_profile)

    assert stored_hash == recomputed_hash
