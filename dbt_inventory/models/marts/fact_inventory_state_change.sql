-- Grain: one row per detected inventory-status transition (restock,
-- stock-out, or any other status change) -- not one row per observation.
-- Observations with no status change from the prior one are excluded.

with changes as (
    select * from {{ ref('int_inventory_state_changes') }}
    where status_changed
),

product_dim as (select * from {{ ref('dim_product') }}),
retailer_dim as (select * from {{ ref('dim_retailer') }}),
date_dim as (select date_key, date_day from {{ ref('dim_date') }})

select
    c.event_id as state_change_event_id,
    p.product_key,
    r.retailer_key,
    d.date_key,
    c.source,
    c.retailer_product_id,
    c.previous_status,
    c.current_status,
    c.restocked,
    c.went_out_of_stock,
    c.previous_observed_at,
    c.observed_at,
    c.hours_since_previous_observation
from changes c
left join product_dim p
    on p.source = c.source and p.retailer_product_id = c.retailer_product_id
left join retailer_dim r on r.source = c.source
left join date_dim d on d.date_day = cast(c.observed_at as date)
