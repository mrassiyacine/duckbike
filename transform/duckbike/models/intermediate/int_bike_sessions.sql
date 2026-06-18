{{ config(materialized='table') }}

with ranked as (
    select
        bike_id,
        snapshot_ts,
        lat,
        lon,
        h3_index,
        battery_pct_0_100,
        is_in_zone,
        is_trip_viable,
        row_number() over (partition by bike_id order by snapshot_ts asc)  as rn_asc,
        row_number() over (partition by bike_id order by snapshot_ts desc) as rn_desc,
        count(*)     over (partition by bike_id)                           as n_snapshots
    from {{ ref('int_bikes_clean') }}
),

first_obs as (
    select
        bike_id,
        snapshot_ts        as first_seen,
        lat                as first_lat,
        lon                as first_lon,
        h3_index           as first_h3,
        battery_pct_0_100  as first_battery
    from ranked
    where rn_asc = 1
),

last_obs as (
    select
        bike_id,
        snapshot_ts        as last_seen,
        lat                as last_lat,
        lon                as last_lon,
        h3_index           as last_h3,
        battery_pct_0_100  as last_battery,
        is_in_zone         as last_is_in_zone,
        is_trip_viable     as last_is_trip_viable,
        n_snapshots
    from ranked
    where rn_desc = 1
)

select
    f.bike_id,

    f.first_seen,
    l.last_seen,

    f.first_lat,
    f.first_lon,
    f.first_h3,
    f.first_battery,

    l.last_lat,
    l.last_lon,
    l.last_h3,
    l.last_battery,
    l.last_is_in_zone,
    l.last_is_trip_viable,

    l.n_snapshots,
    extract(epoch from (l.last_seen - f.first_seen)) / 60.0 as session_duration_min

from first_obs f
join last_obs l on f.bike_id = l.bike_id
