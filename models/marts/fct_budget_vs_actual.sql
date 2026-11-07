-- Budget vs actual for the budget year, by month x account x cost centre x region.
-- variance_ebit_nok > 0 means better than budget (more revenue or less cost).
{% set budget_year = 2025 %}

with pl as (
    select * from {{ ref('int_gl_pl') }}
    where year(month) = {{ budget_year }}
),

pivoted as (
    select
        month,
        account_id,
        account_name,
        account_type,
        pl_line,
        cost_centre_id,
        region_id,
        sum(case when scenario = 'actual' then pl_amount_nok else 0 end) as actual_nok,
        sum(case when scenario = 'budget' then pl_amount_nok else 0 end) as budget_nok,
        sum(case when scenario = 'actual' then ebit_amount_nok else 0 end)
            - sum(case when scenario = 'budget' then ebit_amount_nok else 0 end) as variance_ebit_nok
    from pl
    group by all
)

select
    *,
    actual_nok - budget_nok as variance_nok,
    (actual_nok - budget_nok) / nullif(budget_nok, 0) as variance_pct,
    variance_ebit_nok >= 0 as is_favourable
from pivoted
