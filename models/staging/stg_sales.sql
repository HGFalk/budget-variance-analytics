-- Actuals and budget at the same grain: month x region x product line
with actuals as (
    select 'actual' as scenario, * from {{ source('raw', 'sales_actuals') }}
),

budget as (
    select 'budget' as scenario, * from {{ source('raw', 'sales_budget') }}
),

unioned as (
    select * from actuals
    union all
    select * from budget
)

select
    scenario,
    cast(month as date) as month,
    region_id,
    product_line_id,
    cast(quantity as integer) as quantity,
    cast(revenue_nok as bigint) as revenue_nok,
    cast(cogs_nok as bigint) as cogs_nok
from unioned
