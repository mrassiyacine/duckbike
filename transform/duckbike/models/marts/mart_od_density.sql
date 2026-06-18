{{ config(materialized='table') }}

with counts as (
    select
        h3_index,
        snapshot_ts,
        hour_paris,
        is_weekend,
        count(*) as n_bikes
    from {{ ref('int_bikes_clean') }}
    where is_in_zone
    group by h3_index, snapshot_ts, hour_paris, is_weekend
),

with_prev as (
    select
        h3_index,
        snapshot_ts,
        hour_paris,
        is_weekend,
        n_bikes,
        lag(n_bikes) over (partition by h3_index order by snapshot_ts)    as prev_n_bikes,
        lag(snapshot_ts) over (partition by h3_index order by snapshot_ts) as prev_ts
    from counts
),

deltas as (
    select
        h3_index,
        hour_paris,
        is_weekend,
        n_bikes - prev_n_bikes as delta,
        extract(epoch from (snapshot_ts - prev_ts)) as gap_seconds
    from with_prev
    where prev_ts is not null
      and extract(epoch from (snapshot_ts - prev_ts)) between 300 and 1800
      and abs(n_bikes - prev_n_bikes) <= 8
)

select
    h3_index,
    hour_paris,
    is_weekend,
    round(avg(greatest(0, -delta)), 3) as avg_departures,
    round(avg(greatest(0,  delta)), 3) as avg_arrivals,
    round(avg(delta), 3)               as avg_net_flow,
    count(*)                           as n_observations
from deltas
group by h3_index, hour_paris, is_weekend
