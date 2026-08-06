-- One row per priced observation, annotated with the previous price for the
-- same (source, retailer_product_id) via LAG(), and the resulting percent
-- change. Kept separate from int_inventory_state_changes because price
-- history and stock-status history are analyzed independently downstream
-- (fact_price_observation vs fact_inventory_state_change) and recomputing
-- this LAG() on every dashboard query would be wasteful.

with events as (
    select * from {{ ref('int_inventory_events_deduplicated') }}
    where price is not null
),

with_lag as (
    select
        *,
        lag(price) over (
            partition by source, retailer_product_id order by observed_at
        ) as previous_price,
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
    previous_price,
    price as current_price,
    (previous_price is not null and previous_price != price) as price_changed,
    case
        when previous_price is not null and previous_price != 0
            then round(100.0 * (price - previous_price) / previous_price, 2)
    end as pct_change
from with_lag
