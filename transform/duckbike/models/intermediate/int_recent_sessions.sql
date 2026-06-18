{{ config(materialized='table') }}

select
    row_number() over (order by last_seen, first_seen, bike_id) as sid,
    *
from {{ ref('int_bike_sessions') }}
where first_seen is not null
  and last_seen is not null
  and last_seen >= (select max(last_seen) from {{ ref('int_bike_sessions') }})
                   - interval 1 day * {{ var('trip_lookback_days') }}
