import pandas as pd

from inventory_pipeline.loaders.snowflake import (
    EVENTS_STAGE_COLUMNS,
    RUNS_STAGE_COLUMNS,
    _select_expr,
    _to_timestamp_string,
)


def test_to_timestamp_string_preserves_the_correct_date():
    """Regression test: write_pandas' Arrow/Parquet path corrupted
    datetime64 columns written straight to TIMESTAMP_NTZ (nanosecond/
    microsecond unit-scaling bug against a live Snowflake target -- not
    reproducible without a live connection, but the string transform itself
    must not introduce its own corruption)."""
    series = pd.Series(["2026-08-06T12:00:00+00:00", "2026-05-09T12:00:00+00:00"])

    result = _to_timestamp_string(series)

    assert result.iloc[0] == "2026-08-06 12:00:00.000000"
    assert result.iloc[1] == "2026-05-09 12:00:00.000000"
    assert result.dtype == object  # plain strings, never datetime64


def test_to_timestamp_string_normalizes_non_utc_input_to_utc():
    series = pd.Series(["2026-08-06T05:00:00-07:00"])  # 12:00 UTC

    result = _to_timestamp_string(series)

    assert result.iloc[0] == "2026-08-06 12:00:00.000000"


def test_stage_columns_cover_every_target_column():
    events_names = [name for name, _ in EVENTS_STAGE_COLUMNS]
    runs_names = [name for name, _ in RUNS_STAGE_COLUMNS]

    assert "EVENT_ID" in events_names
    assert "RAW_PAYLOAD" in events_names
    assert "RUN_ID" in runs_names
    assert "ERROR_SUMMARY" in runs_names


def test_select_expr_wraps_timestamps_and_json_but_not_plain_columns():
    assert "TRY_TO_TIMESTAMP_NTZ" in _select_expr("OBSERVED_AT")
    assert "PARSE_JSON" in _select_expr("RAW_PAYLOAD")
    assert _select_expr("PRICE") == "src.PRICE"
