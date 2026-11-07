-- General ledger, actuals and budget.
-- amount_nok keeps the ledger sign: credits (revenue) negative, debits (costs) positive.
with actuals as (
    select 'actual' as scenario, * from {{ source('raw', 'gl_actuals') }}
),

budget as (
    select 'budget' as scenario, * from {{ source('raw', 'gl_budget') }}
),

unioned as (
    select * from actuals
    union all
    select * from budget
)

select
    scenario,
    cast(month as date) as month,
    cast(account_id as integer) as account_id,
    cost_centre_id,
    nullif(region_id, '') as region_id,  -- opex is not split by region
    cast(amount_nok as bigint) as amount_nok
from unioned
