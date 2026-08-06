-- Grain: one row per priced observation, pre-joined to its previous price so
-- price-history charts don't need to recompute LAG() on every query.

with prices as (
    select * from {{ ref('int_product_price_changes') }}
),

product_dim as (select * from {{ ref('dim_product') }}),
retailer_dim as (select * from {{ ref('dim_retailer') }}),
date_dim as (select date_key, date_day from {{ ref('dim_date') }})

select
    p.event_id,
    pd.product_key,
    r.retailer_key,
    d.date_key,
    p.source,
    p.retailer_product_id,
    p.previous_price,
    p.current_price,
    p.price_changed,
    p.pct_change,
    p.previous_observed_at,
    p.observed_at
from prices p
left join product_dim pd
    on pd.source = p.source and pd.retailer_product_id = p.retailer_product_id
left join retailer_dim r on r.source = p.source
left join date_dim d on d.date_day = cast(p.observed_at as date)
