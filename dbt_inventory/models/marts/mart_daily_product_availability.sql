-- Grain: one row per (product, day). Powers the dashboard's availability
-- timeline and per-product summary views.

with daily as (
    select * from {{ ref('int_product_daily_inventory') }}
),

product_dim as (select * from {{ ref('dim_product') }}),
retailer_dim as (select * from {{ ref('dim_retailer') }})

select
    p.product_key,
    r.retailer_key,
    daily.source,
    daily.retailer_product_id,
    p.product_name,
    p.category,
    daily.observation_date,
    daily.observation_count,
    daily.in_stock_observations,
    daily.availability_pct,
    daily.min_price,
    daily.max_price,
    daily.avg_price,
    daily.last_status,
    daily.last_observed_at
from daily
left join product_dim p
    on p.source = daily.source and p.retailer_product_id = daily.retailer_product_id
left join retailer_dim r on r.source = daily.source
