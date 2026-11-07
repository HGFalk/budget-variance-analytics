select
    product_line_id,
    product_line_name,
    unit,
    cast(revenue_account as integer) as revenue_account_id,
    cast(cogs_account as integer) as cogs_account_id
from {{ source('raw', 'dim_product_line') }}
