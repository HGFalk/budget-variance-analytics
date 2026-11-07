select
    cost_centre_id,
    cost_centre_name
from {{ source('raw', 'dim_cost_centre') }}
