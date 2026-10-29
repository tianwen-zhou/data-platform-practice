{% snapshot accounts_snapshot %}
{{ config(unique_key='account_id', strategy='check', check_cols=['last_channel'], target_schema='snapshots') }}
-- Slowly changing dimension (type 2): keeps history whenever an account's latest channel changes.
select account_id, arg_max(channel, created_at) as last_channel
from {{ ref('stg_transactions') }}
group by account_id
{% endsnapshot %}
