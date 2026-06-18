{{ config(materialized='view') }}

with source as (
    select * from {{ source('dott', 'free_bike_status') }}
)


select
    bike_id,
    lat,
    lon,
    battery_pct * 100              as battery_pct_0_100,
    range_km,
    last_reported,
    h3_index,
    snapshot_ts

from source
