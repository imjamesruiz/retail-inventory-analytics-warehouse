select
    {{ dbt_utils.generate_surrogate_key(['retailer_code']) }} as retailer_key,
    retailer_code as source,
    retailer_name,
    website,
    integration_mode
from {{ ref('stg_retailers') }}
