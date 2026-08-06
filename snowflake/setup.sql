-- Retail Inventory Analytics Warehouse -- Snowflake environment setup.
-- Run once, as a role with ACCOUNTADMIN or SECURITYADMIN + SYSADMIN privileges
-- (e.g. in a free trial account this is the default admin role).
--
-- Cost control: XSMALL warehouse, auto-suspend after 60s idle, auto-resume on
-- query, and it starts suspended. A dev/portfolio workload run occasionally
-- for a few minutes at a time should stay well within a trial's free credits.

CREATE WAREHOUSE IF NOT EXISTS RETAIL_INVENTORY_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Warehouse for the Retail Inventory Analytics Warehouse project';

CREATE DATABASE IF NOT EXISTS RETAIL_INVENTORY
  COMMENT = 'Raw and analytics data for retail inventory/pricing observations';

CREATE SCHEMA IF NOT EXISTS RETAIL_INVENTORY.RAW
  COMMENT = 'Immutable landing zone loaded directly by the Python pipeline';

CREATE SCHEMA IF NOT EXISTS RETAIL_INVENTORY.ANALYTICS
  COMMENT = 'dbt-managed staging, intermediate, and mart models';

USE DATABASE RETAIL_INVENTORY;
USE SCHEMA RAW;

-- One row per normalized inventory observation. RAW_PAYLOAD preserves the
-- complete, unmodified source response for full-fidelity replay/debugging;
-- every other column is the already-normalized value from the Python layer.
CREATE TABLE IF NOT EXISTS RAW.INVENTORY_EVENTS (
    EVENT_ID             STRING NOT NULL,
    SOURCE                STRING NOT NULL,
    RETAILER_PRODUCT_ID   STRING NOT NULL,
    PRODUCT_NAME          STRING,
    PRODUCT_URL           STRING,
    SKU                   STRING,
    UPC                   STRING,
    CATEGORY              STRING,
    PRICE                 NUMBER(12, 2),
    CURRENCY              STRING,
    INVENTORY_STATUS      STRING,
    QUANTITY_AVAILABLE    NUMBER,
    STORE_ID              STRING,
    LOCATION_TYPE         STRING,
    OBSERVED_AT           TIMESTAMP_NTZ,
    EXTRACTED_AT          TIMESTAMP_NTZ,
    INGESTION_RUN_ID      STRING,
    RAW_FILE_PATH         STRING,
    SOURCE_RESPONSE_HASH  STRING,
    SCHEMA_VERSION        STRING,
    RAW_PAYLOAD           VARIANT,
    LOADED_AT             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Immutable, append-only inventory/pricing observations. event_id is a deterministic hash of (source, retailer_product_id, observed_at), so MERGE-based loads are idempotent.';

-- One row per extraction run manifest (one run = one source x one simulated
-- or real poll). Powers pipeline observability: freshness, error rates,
-- run success percentage.
CREATE TABLE IF NOT EXISTS RAW.INGESTION_RUNS (
    RUN_ID                   STRING NOT NULL,
    SOURCE                   STRING NOT NULL,
    OBSERVED_AT              TIMESTAMP_NTZ,
    STARTED_AT               TIMESTAMP_NTZ,
    COMPLETED_AT             TIMESTAMP_NTZ,
    STATUS                   STRING,
    PAYLOADS_RECEIVED        NUMBER,
    EVENTS_NORMALIZED        NUMBER,
    EVENTS_REJECTED          NUMBER,
    RAW_PAYLOAD_PATH         STRING,
    NORMALIZED_OUTPUT_PATH   STRING,
    MANIFEST_PATH            STRING,
    ERROR_SUMMARY            VARIANT,
    PIPELINE_VERSION         STRING,
    LOADED_AT                TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'One row per ingestion run manifest; run_id is unique per run so loads are idempotent.';

-- Convenience view: rejected-record diagnostics without granting access to
-- full raw payloads.
CREATE VIEW IF NOT EXISTS RAW.V_RECENT_INGESTION_RUNS AS
SELECT
    RUN_ID,
    SOURCE,
    STARTED_AT,
    COMPLETED_AT,
    STATUS,
    PAYLOADS_RECEIVED,
    EVENTS_NORMALIZED,
    EVENTS_REJECTED,
    PIPELINE_VERSION
FROM RAW.INGESTION_RUNS
ORDER BY STARTED_AT DESC;
