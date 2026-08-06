with source as (
    select * from {{ source('raw', 'ingestion_runs') }}
),

renamed as (
    select
        run_id,
        upper(trim(source)) as source_name,
        observed_at,
        started_at,
        completed_at,
        datediff('second', started_at, completed_at) as duration_seconds,
        case
            when upper(trim(status)) in ('SUCCESS', 'PARTIAL_FAILURE', 'FAILED')
                then upper(trim(status))
            else 'UNKNOWN'
        end as status,
        payloads_received,
        events_normalized,
        events_rejected,
        raw_payload_path,
        normalized_output_path,
        manifest_path,
        error_summary,
        pipeline_version,
        loaded_at
    from source
)

select * from renamed
