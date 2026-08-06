select
    {{ dbt_utils.generate_surrogate_key(['retailer', 'retailer_product_id']) }} as product_key,
    product_id,
    retailer as source,
    retailer_product_id,
    product_name,
    product_url,
    category,
    store_id
from {{ ref('stg_products') }}
