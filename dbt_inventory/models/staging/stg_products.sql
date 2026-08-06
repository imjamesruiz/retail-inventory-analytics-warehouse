-- The tracked-product catalog, loaded as a seed rather than a Snowflake
-- source since it's reference data this project curates, not something the
-- pipeline observes. See dbt_inventory/seeds/seed_products.csv.

with source as (
    select * from {{ ref('seed_products') }}
),

renamed as (
    select
        product_id,
        upper(trim(retailer)) as retailer,
        retailer_product_id,
        product_name,
        product_url,
        category,
        store_id
    from source
)

select * from renamed
