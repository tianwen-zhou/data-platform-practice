-- Staging: clean types, remove upstream duplicates, nothing else.
with source as (
    select * from {{ source('raw', 'transactions') }}
),

deduplicated as (
    select
        *,
        row_number() over (partition by transaction_id order by created_at) as row_num
    from source
)

select
    transaction_id,
    account_id,
    cast(amount_cents as bigint)          as amount_cents,
    channel,
    cast(created_at as timestamp)          as created_at,
    cast(cast(created_at as timestamp) as date) as business_date
from deduplicated
where row_num = 1
