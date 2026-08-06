-- One row per observation, annotated with the immediately preceding
-- observation for the same (source, retailer_product_id) via LAG(), so
-- restocks and stock-outs can be identified without a self-join. Ported
-- from the original bot's diffEngine.ts, expressed as SQL instead of TS.

with events as (
    select * from {{ ref('int_inventory_events_deduplicated') }}
),

with_lag as (
    select
        *,
        lag(inventory_status) over (
            partition by source, retailer_product_id order by observed_at
        ) as previous_status,
        lag(observed_at) over (
            partition by source, retailer_product_id order by observed_at
        ) as previous_observed_at
    from events
)

select
    event_id,
    source,
    retailer_product_id,
    observed_at,
    previous_observed_at,
    previous_status,
    inventory_status as current_status,
    (previous_status is not null and previous_status is distinct from inventory_status)
        as status_changed,
    (previous_status is not null and previous_status != 'IN_STOCK' and inventory_status = 'IN_STOCK')
        as restocked,
    (previous_status = 'IN_STOCK' and inventory_status = 'OUT_OF_STOCK')
        as went_out_of_stock,
    datediff('hour', previous_observed_at, observed_at) as hours_since_previous_observation
from with_lag
