"""Loads normalized events and run manifests from raw storage into Snowflake.

Approach: read every run's NDJSON output via the RawStorage abstraction (so
this works identically against local files or S3), stage the rows into a
Snowflake temporary table with write_pandas, then MERGE into the permanent
table on its deterministic primary key. MERGE with WHEN NOT MATCHED THEN
INSERT (no UPDATE branch) means loading the same run twice, or loading two
runs that happen to overlap, never creates duplicates -- exactly the
idempotency guarantee raw storage's immutability depends on downstream.

Timestamp columns are staged as plain ISO-8601 strings and parsed
server-side with TRY_TO_TIMESTAMP_NTZ during the MERGE, rather than staged
as pandas datetime64 columns. write_pandas' Arrow/Parquet path has a
unit-scaling bug against TIMESTAMP_NTZ targets on some environments (seen
here with snowflake-connector-python 4.7.1 on Python 3.14) that silently
corrupts the stored value into a nonsense date instead of raising -- string
staging sidesteps that code path entirely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from inventory_pipeline.config import Settings
from inventory_pipeline.logging_config import get_logger
from inventory_pipeline.storage.base import RawStorage

logger = get_logger()

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# (column, staging column type). Timestamp columns are STRING here and cast
# with TRY_TO_TIMESTAMP_NTZ on insert; RAW_PAYLOAD/ERROR_SUMMARY are STRING
# here and cast with PARSE_JSON on insert. Everything else matches its type
# in the target RAW table.
EVENTS_STAGE_COLUMNS: list[tuple[str, str]] = [
    ("EVENT_ID", "STRING"),
    ("SOURCE", "STRING"),
    ("RETAILER_PRODUCT_ID", "STRING"),
    ("PRODUCT_NAME", "STRING"),
    ("PRODUCT_URL", "STRING"),
    ("SKU", "STRING"),
    ("UPC", "STRING"),
    ("CATEGORY", "STRING"),
    ("PRICE", "NUMBER(12, 2)"),
    ("CURRENCY", "STRING"),
    ("INVENTORY_STATUS", "STRING"),
    ("QUANTITY_AVAILABLE", "NUMBER"),
    ("STORE_ID", "STRING"),
    ("LOCATION_TYPE", "STRING"),
    ("OBSERVED_AT", "STRING"),
    ("EXTRACTED_AT", "STRING"),
    ("INGESTION_RUN_ID", "STRING"),
    ("RAW_FILE_PATH", "STRING"),
    ("SOURCE_RESPONSE_HASH", "STRING"),
    ("SCHEMA_VERSION", "STRING"),
    ("RAW_PAYLOAD", "STRING"),
]

RUNS_STAGE_COLUMNS: list[tuple[str, str]] = [
    ("RUN_ID", "STRING"),
    ("SOURCE", "STRING"),
    ("OBSERVED_AT", "STRING"),
    ("STARTED_AT", "STRING"),
    ("COMPLETED_AT", "STRING"),
    ("STATUS", "STRING"),
    ("PAYLOADS_RECEIVED", "NUMBER"),
    ("EVENTS_NORMALIZED", "NUMBER"),
    ("EVENTS_REJECTED", "NUMBER"),
    ("RAW_PAYLOAD_PATH", "STRING"),
    ("NORMALIZED_OUTPUT_PATH", "STRING"),
    ("MANIFEST_PATH", "STRING"),
    ("ERROR_SUMMARY", "STRING"),
    ("PIPELINE_VERSION", "STRING"),
]

EVENTS_COLUMNS = [c for c, _ in EVENTS_STAGE_COLUMNS]
RUNS_COLUMNS = [c for c, _ in RUNS_STAGE_COLUMNS]
_TIMESTAMP_COLUMNS = {"OBSERVED_AT", "EXTRACTED_AT", "STARTED_AT", "COMPLETED_AT"}
_JSON_COLUMNS = {"RAW_PAYLOAD", "ERROR_SUMMARY"}


@dataclass
class LoadResult:
    events_loaded: int
    runs_loaded: int
    events_source_files: int
    runs_source_files: int


class SnowflakeLoader:
    def __init__(self, settings: Settings) -> None:
        settings.require_snowflake()
        self.settings = settings

    def _connect(self) -> snowflake.connector.SnowflakeConnection:
        s = self.settings
        kwargs: dict[str, str] = {
            "account": s.snowflake_account,
            "user": s.snowflake_user,
            "role": s.snowflake_role,
            "warehouse": s.snowflake_warehouse,
            "database": s.snowflake_database,
            "schema": s.snowflake_schema,
        }
        if s.snowflake_private_key_path:
            kwargs["private_key_file"] = s.snowflake_private_key_path
        else:
            kwargs["password"] = s.snowflake_password
        return snowflake.connector.connect(**kwargs)

    def load_from_storage(self, storage: RawStorage) -> LoadResult:
        events_df, events_files = _collect_events(storage)
        runs_df, runs_files = _collect_runs(storage)

        conn = self._connect()
        try:
            events_loaded = 0 if events_df.empty else _merge_events(conn, events_df)
            runs_loaded = 0 if runs_df.empty else _merge_runs(conn, runs_df)
        finally:
            conn.close()

        logger.info(
            "snowflake_load_completed",
            events_loaded=events_loaded,
            runs_loaded=runs_loaded,
            events_source_files=events_files,
            runs_source_files=runs_files,
        )
        return LoadResult(events_loaded, runs_loaded, events_files, runs_files)


def _collect_events(storage: RawStorage) -> tuple[pd.DataFrame, int]:
    keys = [k for k in storage.list_keys("raw/") if k.endswith("normalized_events.ndjson")]
    rows: list[dict] = []

    for key in keys:
        norm_text = storage.read_text(key)
        if not norm_text.strip():
            continue

        raw_key = key.replace("normalized_events.ndjson", "raw_payloads.ndjson")
        raw_by_product: dict[str, object] = {}
        if storage.exists(raw_key):
            for line in storage.read_text(raw_key).splitlines():
                if not line.strip():
                    continue
                raw_row = json.loads(line)
                raw_by_product[raw_row["retailer_product_id"]] = raw_row["raw_response"]

        for line in norm_text.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            event["raw_payload"] = json.dumps(raw_by_product.get(event["retailer_product_id"]))
            rows.append(event)

    if not rows:
        return pd.DataFrame(columns=EVENTS_COLUMNS), len(keys)

    df = pd.DataFrame(rows)
    df.columns = [c.upper() for c in df.columns]
    df = df.reindex(columns=EVENTS_COLUMNS)
    for col in ("OBSERVED_AT", "EXTRACTED_AT"):
        df[col] = _to_timestamp_string(df[col])
    return df, len(keys)


def _collect_runs(storage: RawStorage) -> tuple[pd.DataFrame, int]:
    keys = [k for k in storage.list_keys("raw/") if k.endswith("manifest.json")]
    rows: list[dict] = []

    for key in keys:
        manifest = json.loads(storage.read_text(key))
        manifest["error_summary"] = json.dumps(manifest.get("error_summary", []))
        rows.append(manifest)

    if not rows:
        return pd.DataFrame(columns=RUNS_COLUMNS), len(keys)

    df = pd.DataFrame(rows)
    df.columns = [c.upper() for c in df.columns]
    df = df.reindex(columns=RUNS_COLUMNS)
    for col in ("OBSERVED_AT", "STARTED_AT", "COMPLETED_AT"):
        df[col] = _to_timestamp_string(df[col])
    return df, len(keys)


def _to_timestamp_string(series: pd.Series) -> pd.Series:
    """UTC wall-clock ISO string, e.g. '2026-08-06 12:00:00.000000'.

    Kept as plain strings all the way through write_pandas -- see module
    docstring for why datetime64 columns aren't safe here.
    """
    return pd.to_datetime(series, utc=True).dt.tz_localize(None).dt.strftime(_TIMESTAMP_FORMAT)


def _create_stage_table(
    conn: snowflake.connector.SnowflakeConnection, table_name: str, columns: list[tuple[str, str]]
) -> None:
    column_defs = ", ".join(f"{name} {sql_type}" for name, sql_type in columns)
    with conn.cursor() as cur:
        cur.execute(f"CREATE OR REPLACE TEMPORARY TABLE {table_name} ({column_defs})")


def _select_expr(column: str) -> str:
    if column in _JSON_COLUMNS:
        return f"PARSE_JSON(src.{column})"
    if column in _TIMESTAMP_COLUMNS:
        return f"TRY_TO_TIMESTAMP_NTZ(src.{column})"
    return f"src.{column}"


def _merge_events(conn: snowflake.connector.SnowflakeConnection, df: pd.DataFrame) -> int:
    stage_table = "INVENTORY_EVENTS_STAGE"
    _create_stage_table(conn, stage_table, EVENTS_STAGE_COLUMNS)
    write_pandas(conn, df, table_name=stage_table, quote_identifiers=False)

    select_exprs = [_select_expr(c) for c in EVENTS_COLUMNS]
    merge_sql = f"""
        MERGE INTO RAW.INVENTORY_EVENTS AS tgt
        USING {stage_table} AS src
        ON tgt.EVENT_ID = src.EVENT_ID
        WHEN NOT MATCHED THEN INSERT ({", ".join(EVENTS_COLUMNS)})
        VALUES ({", ".join(select_exprs)})
    """
    with conn.cursor() as cur:
        cur.execute(merge_sql)
        return cur.rowcount or 0


def _merge_runs(conn: snowflake.connector.SnowflakeConnection, df: pd.DataFrame) -> int:
    stage_table = "INGESTION_RUNS_STAGE"
    _create_stage_table(conn, stage_table, RUNS_STAGE_COLUMNS)
    write_pandas(conn, df, table_name=stage_table, quote_identifiers=False)

    select_exprs = [_select_expr(c) for c in RUNS_COLUMNS]
    merge_sql = f"""
        MERGE INTO RAW.INGESTION_RUNS AS tgt
        USING {stage_table} AS src
        ON tgt.RUN_ID = src.RUN_ID
        WHEN NOT MATCHED THEN INSERT ({", ".join(RUNS_COLUMNS)})
        VALUES ({", ".join(select_exprs)})
    """
    with conn.cursor() as cur:
        cur.execute(merge_sql)
        return cur.rowcount or 0
