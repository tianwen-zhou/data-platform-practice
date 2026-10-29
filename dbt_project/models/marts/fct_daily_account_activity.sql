-- Mart: one row per account per business date.
-- Incremental: on later runs only the dates that are newer than what is already loaded are processed.
{{ config(materialized='incremental', unique_key=['account_id', 'business_date']) }}

select
    account_id,
    business_date,
    count(*)                                         as transaction_count,
    sum(amount_cents)                                as net_amount_cents,
    sum(case when amount_cents < 0 then 1 else 0 end) as debit_count
from {{ ref('stg_transactions') }}
{% if is_incremental() %}
where business_date >= (select max(business_date) from {{ this }})
{% endif %}
group by account_id, business_date
