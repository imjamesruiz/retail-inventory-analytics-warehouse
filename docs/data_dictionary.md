# Data Dictionary

Full column-level documentation also lives in each layer's `schema.yml`
(`dbt_inventory/models/*/*.yml`) and is rendered by `make dbt-docs`. This file
is the human-readable summary, organized by layer.

## Raw layer (`RAW` schema, loaded by Python)

### `RAW.INVENTORY_EVENTS`
Grain: one row per inventory/pricing observation.

| Column | Type | Notes |
|---|---|---|
| `EVENT_ID` | STRING | `uuid5(source, retailer_product_id, observed_at)` -- deterministic |
| `SOURCE` | STRING | Retailer code |
| `RETAILER_PRODUCT_ID` | STRING | Retailer's own product identifier |
| `PRODUCT_NAME`, `PRODUCT_URL`, `SKU`, `UPC`, `CATEGORY` | STRING | May be null depending on source |
| `PRICE` | NUMBER(12,2) | Null if not present in the response |
| `CURRENCY` | STRING | Always `USD` in this project |
| `INVENTORY_STATUS` | STRING | `IN_STOCK`, `OUT_OF_STOCK`, `PREORDER`, `BACKORDER`, `UNKNOWN` |
| `QUANTITY_AVAILABLE` | NUMBER | Null when the source doesn't expose it |
| `STORE_ID`, `LOCATION_TYPE` | STRING | Store-level fields, mostly null (online-only sources) |
| `OBSERVED_AT` | TIMESTAMP_NTZ | When the observation was taken (UTC) |
| `EXTRACTED_AT` | TIMESTAMP_NTZ | When the Python pipeline processed it |
| `INGESTION_RUN_ID` | STRING | FK to `INGESTION_RUNS.RUN_ID` |
| `RAW_FILE_PATH`, `SOURCE_RESPONSE_HASH`, `SCHEMA_VERSION` | STRING | Provenance/audit fields |
| `RAW_PAYLOAD` | VARIANT | Complete, unmodified source response |
| `LOADED_AT` | TIMESTAMP_NTZ | Snowflake load time |

### `RAW.INGESTION_RUNS`
Grain: one row per extraction run (one source x one poll/simulated day).

| Column | Type | Notes |
|---|---|---|
| `RUN_ID` | STRING | Unique per run |
| `SOURCE` | STRING | Retailer code |
| `OBSERVED_AT` | TIMESTAMP_NTZ | The simulated/real timestamp this run represents |
| `STARTED_AT`, `COMPLETED_AT` | TIMESTAMP_NTZ | Wall-clock run duration |
| `STATUS` | STRING | `SUCCESS`, `PARTIAL_FAILURE`, `FAILED` |
| `PAYLOADS_RECEIVED`, `EVENTS_NORMALIZED`, `EVENTS_REJECTED` | NUMBER | Run-level counts |
| `ERROR_SUMMARY` | VARIANT | Up to 10 rejection reasons |
| `PIPELINE_VERSION` | STRING | For tracing which code version produced a run |

## Staging layer (`ANALYTICS_STAGING`)

- **`stg_inventory_events`** -- `RAW.INVENTORY_EVENTS` renamed/cast/standardized. Same grain.
- **`stg_ingestion_runs`** -- `RAW.INGESTION_RUNS` renamed/cast/standardized, plus `duration_seconds`.
- **`stg_products`** -- from `seed_products.csv`, the tracked-product catalog.
- **`stg_retailers`** -- from `seed_retailers.csv`, retailer reference data.

## Intermediate layer (`ANALYTICS_INTERMEDIATE`)

- **`int_inventory_events_deduplicated`** -- *incremental*. Deduplicated
  observations, one row per `event_id`. The base table for everything downstream.
- **`int_inventory_state_changes`** -- one row per observation, annotated with
  the previous observation's status via `LAG()`, plus `restocked` /
  `went_out_of_stock` boolean flags.
- **`int_product_price_changes`** -- one row per priced observation, annotated
  with the previous price via `LAG()` and the percent change.
- **`int_product_daily_inventory`** -- one row per `(source,
  retailer_product_id, observation_date)`: observation count, in-stock rate,
  price range, last known status of the day.

## Marts layer (`ANALYTICS_MARTS`)

| Table | Grain |
|---|---|
| `dim_product` | One row per `(source, retailer_product_id)` |
| `dim_retailer` | One row per retailer |
| `dim_date` | One row per calendar day, 2024-01-01 to +1 year |
| `fact_inventory_observation` | One row per observation (`event_id`) -- the largest fact table |
| `fact_inventory_state_change` | One row per detected status transition (not every observation) |
| `fact_price_observation` | One row per priced observation, pre-joined to its previous price |
| `mart_daily_product_availability` | One row per `(product, day)` |
| `mart_retailer_summary` | One row per retailer -- pipeline health + average availability |

`fact_inventory_observation` and `fact_price_observation` are deliberately not
merged: the former is the complete observation stream (every poll, any status),
the latter pre-computes the price-history-specific `LAG()`/percent-change
columns so a price chart never needs to recompute a window function.
