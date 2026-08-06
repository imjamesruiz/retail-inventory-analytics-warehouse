-- Singular test: cross-checks the Python pipeline's own bookkeeping
-- (raw.ingestion_runs.events_normalized, written by the extractor) against
-- what actually landed in the warehouse for that run. A mismatch means
-- either the Snowflake loader dropped rows or dbt's dedup logic collapsed
-- more than it should have -- both are bugs worth failing the build over.

with run_totals as (
    select ingestion_run_id, count(*) as fact_event_count
    from {{ ref('fact_inventory_observation') }}
    group by 1
),

manifest_totals as (
    select run_id, events_normalized
    from {{ ref('stg_ingestion_runs') }}
)

select
    m.run_id,
    m.events_normalized,
    coalesce(r.fact_event_count, 0) as fact_event_count
from manifest_totals m
left join run_totals r on r.ingestion_run_id = m.run_id
where m.events_normalized != coalesce(r.fact_event_count, 0)
