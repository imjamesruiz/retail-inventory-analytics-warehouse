{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        on_schema_change='sync_all_columns'
    )
}}

-- The one large historical fact-like model in this project: every
-- deduplicated inventory observation, growing by every ingestion run.
-- Incremental so a full backfill only happens once; every later run only
-- (re)processes recent observed_at values.
--
-- Late-arriving data: rather than filtering strictly to
-- `observed_at > max(observed_at)`, incremental runs re-scan a 48-hour
-- lookback window. A record whose observed_at falls in that window is
-- reprocessed and MERGEd on event_id, so a duplicate never lands even
-- though it's read twice -- this is what makes the lookback safe.

with deduplicated as (
    select
        *,
        row_number() over (
            partition by event_id
            order by loaded_at desc
        ) as rn
    from {{ ref('stg_inventory_events') }}
    {% if is_incremental() %}
    where observed_at > (
        select dateadd('hour', -48, max(observed_at)) from {{ this }}
    )
    {% endif %}
)

select
    event_id,
    source_name as source,
    retailer_product_id,
    product_name,
    product_url,
    sku,
    upc,
    category,
    price,
    currency,
    inventory_status,
    quantity_available,
    store_id,
    location_type,
    observed_at,
    extracted_at,
    ingestion_run_id,
    raw_file_path,
    source_response_hash,
    schema_version,
    loaded_at
from deduplicated
where rn = 1
