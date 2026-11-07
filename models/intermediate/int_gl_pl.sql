-- Adds account attributes and converts ledger signs to P&L signs.
-- pl_amount_nok: revenue and costs both positive (how a P&L is read)
-- ebit_amount_nok: revenue positive, costs negative (sums to EBIT)
select
    gl.scenario,
    gl.month,
    gl.account_id,
    a.account_name,
    a.account_type,
    a.pl_line,
    gl.cost_centre_id,
    gl.region_id,
    gl.amount_nok,
    case when a.account_type = 'Revenue' then -gl.amount_nok else gl.amount_nok end as pl_amount_nok,
    -gl.amount_nok as ebit_amount_nok
from {{ ref('stg_gl') }} as gl
inner join {{ ref('stg_accounts') }} as a
    on gl.account_id = a.account_id
