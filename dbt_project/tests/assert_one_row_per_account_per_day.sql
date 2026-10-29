-- Singular test: returns rows only when the grain is broken.
select account_id, business_date, count(*) as n
from {{ ref('fct_daily_account_activity') }}
group by account_id, business_date
having count(*) > 1
