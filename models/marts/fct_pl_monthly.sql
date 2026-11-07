-- Monthly P&L, actuals 2023 to 2025 and budget 2025, one row per
-- scenario x month x account x cost centre x region
select
    p.scenario,
    p.month,
    p.account_id,
    p.account_name,
    p.account_type,
    p.pl_line,
    p.cost_centre_id,
    cc.cost_centre_name,
    p.region_id,
    r.region_name,
    p.pl_amount_nok,
    p.ebit_amount_nok
from {{ ref('int_gl_pl') }} as p
left join {{ ref('stg_cost_centres') }} as cc on p.cost_centre_id = cc.cost_centre_id
left join {{ ref('stg_regions') }} as r on p.region_id = r.region_id
