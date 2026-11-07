select
    cast(account_id as integer) as account_id,
    account_name,
    account_type,
    pl_line
from {{ source('raw', 'dim_account') }}
