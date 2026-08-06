-- Renames, casts, and standardizes raw.inventory_events. No deduplication or
-- business logic here (see int_inventory_events_deduplicated for that) --
-- staging's job is purely to make the source data consistent to build on.

with source as (
    select * from {{ source('raw', 'inventory_events') }}
),

renamed as (
    select
        event_id,
        upper(trim(source)) as source_name,
        retailer_product_id,
        product_name,
        product_url,
        sku,
        upc,
        category,
        cast(price as numeric(12, 2)) as price,
        -- Every fixture and live source in this project prices in USD; if a
        -- source without a currency field is added, default here rather
        -- than pushing nulls downstream into money math.
        coalesce(nullif(upper(trim(currency)), ''), 'USD') as currency,
        case
            when upper(trim(inventory_status)) in
                ('IN_STOCK', 'OUT_OF_STOCK', 'PREORDER', 'BACKORDER') then upper(trim(inventory_status))
            else 'UNKNOWN'
        end as inventory_status,
        quantity_available,
        store_id,
        coalesce(nullif(upper(trim(location_type)), ''), 'UNKNOWN') as location_type,
        observed_at,
        extracted_at,
        ingestion_run_id,
        raw_file_path,
        source_response_hash,
        schema_version,
        raw_payload,
        loaded_at
    from source
)

select * from renamed
