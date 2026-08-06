-- One row per (source, retailer_product_id, day): observation count,
-- in-stock rate, price range, and the last known status of the day. Feeds
-- mart_daily_product_availability.

with events as (
    select * from {{ ref('int_inventory_events_deduplicated') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by source, retailer_product_id, cast(observed_at as date)
            order by observed_at desc
        ) as rn_desc
    from events
),

daily as (
    select
        source,
        retailer_product_id,
        cast(observed_at as date) as observation_date,
        count(*) as observation_count,
        sum(case when inventory_status = 'IN_STOCK' then 1 else 0 end) as in_stock_observations,
        min(price) as min_price,
        max(price) as max_price,
        avg(price) as avg_price,
        max(observed_at) as last_observed_at
    from ranked
    group by 1, 2, 3
),

last_status_per_day as (
    select
        source,
        retailer_product_id,
        cast(observed_at as date) as observation_date,
        inventory_status as last_status
    from ranked
    where rn_desc = 1
)

select
    d.source,
    d.retailer_product_id,
    d.observation_date,
    d.observation_count,
    d.in_stock_observations,
    round(100.0 * d.in_stock_observations / nullif(d.observation_count, 0), 1) as availability_pct,
    d.min_price,
    d.max_price,
    d.avg_price,
    d.last_observed_at,
    l.last_status
from daily d
join last_status_per_day l
    using (source, retailer_product_id, observation_date)
