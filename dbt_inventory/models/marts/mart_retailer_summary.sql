-- Grain: one row per retailer. Powers the dashboard's pipeline-health view:
-- run success rate, error volume, freshness, and average availability.

with runs as (
    select * from {{ ref('stg_ingestion_runs') }}
),

run_stats as (
    select
        source_name as source,
        count(*) as total_runs,
        sum(case when status = 'SUCCESS' then 1 else 0 end) as successful_runs,
        sum(case when status = 'PARTIAL_FAILURE' then 1 else 0 end) as partial_failure_runs,
        sum(case when status = 'FAILED' then 1 else 0 end) as failed_runs,
        sum(events_normalized) as total_events_normalized,
        sum(events_rejected) as total_events_rejected,
        avg(duration_seconds) as avg_run_duration_seconds,
        max(observed_at) as last_observed_at
    from runs
    group by 1
),

availability as (
    select
        source,
        avg(availability_pct) as avg_availability_pct
    from {{ ref('int_product_daily_inventory') }}
    group by 1
),

retailer_dim as (select * from {{ ref('dim_retailer') }})

select
    r.retailer_key,
    r.source,
    r.retailer_name,
    r.integration_mode,
    rs.total_runs,
    rs.successful_runs,
    rs.partial_failure_runs,
    rs.failed_runs,
    round(100.0 * (rs.successful_runs + rs.partial_failure_runs) / nullif(rs.total_runs, 0), 1)
        as run_success_rate_pct,
    rs.total_events_normalized,
    rs.total_events_rejected,
    rs.avg_run_duration_seconds,
    rs.last_observed_at,
    datediff('hour', rs.last_observed_at, current_timestamp()) as hours_since_last_observation,
    a.avg_availability_pct
from retailer_dim r
left join run_stats rs on rs.source = r.source
left join availability a on a.source = r.source
