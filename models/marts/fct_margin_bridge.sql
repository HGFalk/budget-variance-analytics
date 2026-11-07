-- Gross margin bridge, budget 2025 to actual 2025, in long format for a
-- Power BI waterfall. Grain: month x region x product line x step.
--
--   Volume = (AQ - BQ) x BP x m            more or fewer units, at the average budget margin m
--   Mix    = (AQ - BQ) x BP x (gm% - m)    extra margin because the volume change hit lines with
--                                          above or below average margin (gm% = line budget margin %)
--   Price  = (AP - BP) x AQ                realised price vs budget price
--   Cost   = -(AC - BC) x AQ               unit cost vs budget unit cost
--
-- AQ/BQ actual/budget quantity, AP/BP and AC/BC actual/budget price and unit cost per unit.
-- The four steps add up exactly to actual minus budget gross margin for any slice.
{% set budget_year = 2025 %}

with sales as (
    select * from {{ ref('stg_sales') }}
    where year(month) = {{ budget_year }}
),

paired as (
    select
        b.month,
        b.region_id,
        b.product_line_id,
        b.quantity as bq,
        b.revenue_nok / b.quantity as bp,
        b.cogs_nok / b.quantity as bc,
        a.quantity as aq,
        a.revenue_nok / a.quantity as ap,
        a.cogs_nok / a.quantity as ac,
        b.revenue_nok - b.cogs_nok as budget_gm,
        a.revenue_nok - a.cogs_nok as actual_gm
    from sales as b
    inner join sales as a
        on b.month = a.month
        and b.region_id = a.region_id
        and b.product_line_id = a.product_line_id
        and a.scenario = 'actual'
    where b.scenario = 'budget'
),

avg_margin as (
    select sum(budget_gm) / sum(bq * bp) as m from paired
),

effects as (
    select
        p.*,
        (p.aq - p.bq) * p.bp * am.m as volume_effect,
        (p.aq - p.bq) * (p.bp - p.bc) - (p.aq - p.bq) * p.bp * am.m as mix_effect,
        (p.ap - p.bp) * p.aq as price_effect,
        -(p.ac - p.bc) * p.aq as cost_effect
    from paired as p
    cross join avg_margin as am
),

long as (
    select month, region_id, product_line_id, 1 as step_order, 'Budget gross margin' as step, budget_gm as amount_nok from effects
    union all
    select month, region_id, product_line_id, 2, 'Volume', volume_effect from effects
    union all
    select month, region_id, product_line_id, 3, 'Mix', mix_effect from effects
    union all
    select month, region_id, product_line_id, 4, 'Price', price_effect from effects
    union all
    select month, region_id, product_line_id, 5, 'Unit cost', cost_effect from effects
)

select
    l.month,
    l.region_id,
    r.region_name,
    l.product_line_id,
    pl.product_line_name,
    l.step_order,
    l.step,
    l.amount_nok
from long as l
left join {{ ref('stg_regions') }} as r on l.region_id = r.region_id
left join {{ ref('stg_product_lines') }} as pl on l.product_line_id = pl.product_line_id
