-- Grain: one row per inventory/pricing observation (= one row per event_id).

with events as (
    select * from {{ ref('int_inventory_events_deduplicated') }}
),

product_dim as (select * from {{ ref('dim_product') }}),
retailer_dim as (select * from {{ ref('dim_retailer') }}),
date_dim as (select date_key, date_day from {{ ref('dim_date') }})

select
    e.event_id,
    p.product_key,
    r.retailer_key,
    d.date_key,
    e.source,
    e.retailer_product_id,
    e.price,
    e.currency,
    e.inventory_status,
    e.quantity_available,
    e.store_id,
    e.location_type,
    e.observed_at,
    e.extracted_at,
    e.ingestion_run_id
from events e
left join product_dim p
    on p.source = e.source and p.retailer_product_id = e.retailer_product_id
left join retailer_dim r on r.source = e.source
left join date_dim d on d.date_day = cast(e.observed_at as date)
