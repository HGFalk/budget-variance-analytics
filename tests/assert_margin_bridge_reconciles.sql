-- Budget gross margin plus the four bridge steps must equal actual gross
-- margin from the P&L (tolerance 1 NOK for rounding).
with bridge as (
    select sum(amount_nok) as bridge_total from {{ ref('fct_margin_bridge') }}
),

actual as (
    select sum(ebit_amount_nok) as actual_gm
    from {{ ref('int_gl_pl') }}
    where scenario = 'actual'
      and year(month) = 2025
      and account_type in ('Revenue', 'COGS')
)

select *
from bridge
cross join actual
where abs(bridge_total - actual_gm) > 1
