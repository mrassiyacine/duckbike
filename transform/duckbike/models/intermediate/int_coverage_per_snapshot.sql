{{ config(materialized='table') }}

with usable_bikes as (

    select
        h3_index as bike_h3,
        snapshot_ts
    from {{ ref('int_bikes_clean') }}
    where is_in_zone
      and is_trip_viable
),

reachable_pairs as (

    select
        b.snapshot_ts,
        wtm.destination_h3 as h3_cell,
        wtm.walk_minutes
    from usable_bikes b
    join {{ source('routing', 'walk_time_matrix') }} wtm
      on b.bike_h3 = wtm.origin_h3
    where wtm.walk_minutes <= 10
)

select
    snapshot_ts,
    h3_cell,
    min(walk_minutes)            as nearest_walk_minutes,
    bool_or(walk_minutes <= 5)   as is_covered_5min,
    bool_or(walk_minutes <= 10)  as is_covered_10min
from reachable_pairs
group by snapshot_ts, h3_cell