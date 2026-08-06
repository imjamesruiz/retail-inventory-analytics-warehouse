"""Loads normalized events and run manifests from raw storage into Snowflake.

Approach: read every run's NDJSON output via the RawStorage abstraction (so
this works identically against local files or S3), stage the rows into a
Snowflake temporary table with write_pandas, then MERGE into the permanent
table on its deterministic primary key. MERGE with WHEN NOT MATCHED THEN
INSERT (no UPDATE branch) means loading the same run twice, or loading two
runs that happen to overlap, never creates duplicates -- exactly the
idempotency guarantee raw storage's immutability depends on downstream.
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

EVENTS_COLUMNS = [
    "EVENT_ID",
    "SOURCE",
    "RETAILER_PRODUCT_ID",
    "PRODUCT_NAME",
    "PRODUCT_URL",
    "SKU",
    "UPC",
    "CATEGORY",
    "PRICE",
    "CURRENCY",
    "INVENTORY_STATUS",
    "QUANTITY_AVAILABLE",
    "STORE_ID",
    "LOCATION_TYPE",
    "OBSERVED_AT",
    "EXTRACTED_AT",
    "INGESTION_RUN_ID",
    "RAW_FILE_PATH",
    "SOURCE_RESPONSE_HASH",
    "SCHEMA_VERSION",
    "RAW_PAYLOAD",
]

RUNS_COLUMNS = [
    "RUN_ID",
    "SOURCE",
    "OBSERVED_AT",
    "STARTED_AT",
    "COMPLETED_AT",
    "STATUS",
    "PAYLOADS_RECEIVED",
    "EVENTS_NORMALIZED",
    "EVENTS_REJECTED",
    "RAW_PAYLOAD_PATH",
    "NORMALIZED_OUTPUT_PATH",
    "MANIFEST_PATH",
    "ERROR_SUMMARY",
    "PIPELINE_VERSION",
]


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
        df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
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
        df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
    return df, len(keys)


def _merge_events(conn: snowflake.connector.SnowflakeConnection, df: pd.DataFrame) -> int:
    stage_table = "INVENTORY_EVENTS_STAGE"
    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMPORARY TABLE {stage_table} LIKE RAW.INVENTORY_EVENTS")

    write_pandas(conn, df, table_name=stage_table, quote_identifiers=False)

    insert_cols = [c for c in EVENTS_COLUMNS]
    select_exprs = [
        "PARSE_JSON(src.RAW_PAYLOAD)" if c == "RAW_PAYLOAD" else f"src.{c}" for c in insert_cols
    ]
    merge_sql = f"""
        MERGE INTO RAW.INVENTORY_EVENTS AS tgt
        USING {stage_table} AS src
        ON tgt.EVENT_ID = src.EVENT_ID
        WHEN NOT MATCHED THEN INSERT ({", ".join(insert_cols)})
        VALUES ({", ".join(select_exprs)})
    """
    with conn.cursor() as cur:
        cur.execute(merge_sql)
        return cur.rowcount or 0


def _merge_runs(conn: snowflake.connector.SnowflakeConnection, df: pd.DataFrame) -> int:
    stage_table = "INGESTION_RUNS_STAGE"
    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMPORARY TABLE {stage_table} LIKE RAW.INGESTION_RUNS")

    write_pandas(conn, df, table_name=stage_table, quote_identifiers=False)

    insert_cols = [c for c in RUNS_COLUMNS]
    select_exprs = [
        "PARSE_JSON(src.ERROR_SUMMARY)" if c == "ERROR_SUMMARY" else f"src.{c}" for c in insert_cols
    ]
    merge_sql = f"""
        MERGE INTO RAW.INGESTION_RUNS AS tgt
        USING {stage_table} AS src
        ON tgt.RUN_ID = src.RUN_ID
        WHEN NOT MATCHED THEN INSERT ({", ".join(insert_cols)})
        VALUES ({", ".join(select_exprs)})
    """
    with conn.cursor() as cur:
        cur.execute(merge_sql)
        return cur.rowcount or 0
