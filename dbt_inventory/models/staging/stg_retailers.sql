with source as (
    select * from {{ ref('seed_retailers') }}
),

renamed as (
    select
        upper(trim(retailer_code)) as retailer_code,
        retailer_name,
        website,
        upper(trim(integration_mode)) as integration_mode
    from source
)

select * from renamed
