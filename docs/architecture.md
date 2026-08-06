# Architecture

## Components and responsibilities

| Component | Responsibility |
|---|---|
| `src/inventory_pipeline/extractors/` | One class per retailer, implementing `BaseExtractor`. `fetch_payloads()` gets raw data (fixture or live); `normalize_payload()` turns it into a canonical `InventoryEvent`. Malformed payloads become `RejectedRecord`s, never silently dropped exceptions. |
| `src/inventory_pipeline/normalizers/` | Pure functions mapping one retailer's raw JSON shape to canonical fields -- ported from the original bot's TypeScript status-mapping functions. |
| `src/inventory_pipeline/storage/` | `RawStorage` interface with local filesystem and S3 implementations. Owns the partitioned, append-only key layout and the "never overwrite raw data" guarantee. |
| `src/inventory_pipeline/loaders/snowflake.py` | Reads every run's NDJSON output through the `RawStorage` interface (backend-agnostic), stages it with `write_pandas`, and `MERGE`s into `RAW.*` on a deterministic key. |
| `src/inventory_pipeline/pipeline.py` | Orchestrates one full ingestion run across every source, optionally backfilling N simulated days (fixture mode only). |
| `dbt_inventory/` | All SQL transformation, from `RAW.*` sources to the dimensional mart layer, plus every data test. |
| `dashboard/` | Streamlit app querying the mart layer only. |

## Why this extraction design differs slightly from the proposed file list

The original plan called for a generic `extractors/fixture.py` base class. In
practice, every retailer's fixture and live paths share the same normalization
logic and only differ in `fetch_payloads()`, so each retailer extractor
(`target.py`, `walmart.py`, `pokemon_center.py`, `gamestop.py`) internally
branches on `DataSourceMode` rather than existing as two parallel class
hierarchies. `extractors/fixture_data.py` holds the shared deterministic
payload generators. This avoids a second inheritance axis for four sources
that doesn't pay for itself at this scale.

## Snowflake schema layout

```
RETAIL_INVENTORY (database)
├── RAW                     -- loaded directly by the Python pipeline
│   ├── INVENTORY_EVENTS    -- one row per observation, RAW_PAYLOAD variant column
│   ├── INGESTION_RUNS      -- one row per extraction run manifest
│   └── V_RECENT_INGESTION_RUNS
├── ANALYTICS_STAGING       -- dbt: renamed/cast/standardized
├── ANALYTICS_INTERMEDIATE  -- dbt: dedup, state changes, price changes, daily rollups
├── ANALYTICS_MARTS         -- dbt: dim_*, fact_*, mart_*
└── ANALYTICS_SEEDS         -- dbt: seed_products, seed_retailers
```

The four `ANALYTICS_*` schemas are created automatically by dbt's custom schema
naming (`+schema: staging` etc. in `dbt_project.yml`, appended to the
`SNOWFLAKE_SCHEMA_ANALYTICS` target schema from `profiles.yml`) -- this is why
`roles.sql` grants `CREATE SCHEMA` at the database level rather than
pre-creating each one.

## Idempotency and deduplication, end to end

1. **Raw storage:** every run writes to `raw/source=<X>/.../run_id=<uuid>/`.
   Writing to an existing `run_id` prefix raises `FileExistsError` -- raw data is
   never overwritten, but a fresh run (fresh UUID) is always allowed.
2. **Event identity:** `event_id` is `uuid5(source, retailer_product_id,
   observed_at)` -- deterministic, not random. Two extraction runs that happen
   to observe the same product at the same timestamp produce the same
   `event_id`.
3. **Snowflake load:** the loader stages rows and `MERGE ... WHEN NOT MATCHED
   THEN INSERT` on `event_id` (events table) / `run_id` (runs table). No
   `UPDATE` branch -- observations are immutable facts, so there's nothing to
   update, only insert-if-new. Re-running `load-snowflake` against the same raw
   files is a no-op the second time.
4. **dbt dedup:** `int_inventory_events_deduplicated` additionally guards
   against exact-duplicate rows reaching `RAW.INVENTORY_EVENTS` (e.g. from a
   loader retry) with `ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY
   loaded_at DESC)`, keeping one row per `event_id`.

## Incremental model and late-arriving data

`int_inventory_events_deduplicated` is the one incremental model
(`unique_key='event_id'`, `incremental_strategy='merge'`). On an incremental
run, it doesn't filter strictly to `observed_at > MAX(observed_at)` -- it
re-scans a 48-hour lookback window (`observed_at > MAX(observed_at) - 48h`).
Records in that window get re-read and re-processed, but the `MERGE` on
`event_id` means re-processing them is a no-op if they already landed. This is
what makes it safe to also handle a load that lands a bit late (e.g., a
scheduled run that failed and was retried the next day).

## CI: Snowflake key-pair authentication setup

Local development uses password auth (simplest for a single developer).
GitHub Actions uses key-pair auth instead, since long-lived passwords in CI
secrets are a weaker posture than a key that can be scoped and rotated
independently:

```bash
# 1. Generate an unencrypted private key + matching public key
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_ci_key.p8 -nocrypt
openssl rsa -in snowflake_ci_key.p8 -pubout -out snowflake_ci_key.pub

# 2. Register the public key on the CI service user (run in Snowflake, as an admin role)
#    -- paste the contents of snowflake_ci_key.pub, minus the PEM header/footer, as one line:
#    ALTER USER RETAIL_INVENTORY_CI_USER SET RSA_PUBLIC_KEY='<key contents>';
#    (see the commented-out CREATE USER block in snowflake/roles.sql)

# 3. Store the PRIVATE key as a GitHub Actions secret
gh secret set SNOWFLAKE_PRIVATE_KEY < snowflake_ci_key.p8
```

## GitHub Actions secrets checklist

Set these in the repo's Settings -> Secrets and variables -> Actions:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER` (the CI service user, e.g. `RETAIL_INVENTORY_CI_USER`)
- `SNOWFLAKE_PRIVATE_KEY` (contents of the `.p8` file from the steps above)
- `SNOWFLAKE_ROLE` (`RETAIL_INVENTORY_ROLE`)
- `SNOWFLAKE_WAREHOUSE` (`RETAIL_INVENTORY_WH`)
- `SNOWFLAKE_DATABASE` (`RETAIL_INVENTORY`)
- `SNOWFLAKE_SCHEMA` (`RAW`)
- `SNOWFLAKE_SCHEMA_ANALYTICS` (`CI_ANALYTICS` -- a separate schema from local dev, so CI runs never collide with your local `ANALYTICS_*` schemas)
- `WALMART_API_KEY` (optional, only needed for live-mode scheduled runs)

Without these, `pr-validation.yml`'s `dbt-build` job and `scheduled-pipeline.yml`
are both skipped (their `if:` conditions check for `SNOWFLAKE_ACCOUNT`) --
lint, unit tests, and `dbt parse` still run on every PR regardless.
