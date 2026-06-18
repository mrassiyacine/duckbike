{{ config(materialized='table') }}


select
    snapshot_ts,
    hour_paris,
    is_weekend,

    count(*)                                                       as n_reported,

    count(*) filter (where is_in_zone and is_trip_viable)          as n_effective,
    count(*) filter (where not is_in_zone)                         as n_out_of_zone,
    count(*) filter (where not is_trip_viable)                     as n_low_battery,

    count(*) - count(*) filter (where is_in_zone and is_trip_viable) as n_theatrical,

    (1.0 - count(*) filter (where is_in_zone and is_trip_viable) * 1.0
         / nullif(count(*), 0)) * 100                              as pct_theatrical

from {{ ref('int_bikes_clean') }}
group by snapshot_ts, hour_paris, is_weekend
order by snapshot_ts
