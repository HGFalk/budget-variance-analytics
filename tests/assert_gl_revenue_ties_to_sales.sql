-- Revenue and COGS in the general ledger must equal the sales ledger,
-- by scenario and month. Returns the months that do not tie.
with gl as (
    select
        scenario,
        month,
        sum(case when account_type = 'Revenue' then pl_amount_nok else 0 end) as revenue,
        sum(case when account_type = 'COGS' then pl_amount_nok else 0 end) as cogs
    from {{ ref('int_gl_pl') }}
    group by all
),

sales as (
    select scenario, month, sum(revenue_nok) as revenue, sum(cogs_nok) as cogs
    from {{ ref('stg_sales') }}
    group by all
)

select *
from gl
full outer join sales using (scenario, month)
where coalesce(gl.revenue, 0) <> coalesce(sales.revenue, 0)
   or coalesce(gl.cogs, 0) <> coalesce(sales.cogs, 0)
