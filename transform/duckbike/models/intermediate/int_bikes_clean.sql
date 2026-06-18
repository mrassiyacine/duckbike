{{config(materialized='table')}}

with bikes as (
    select * from {{ref('stg_free_bikes')}}
),
zone as (
    select
        st_geomfromgeojson(geometry) as geometry
    from {{ref('dott_paris_operator_zones')}}
),
enriched as (
    select
        b.*,
        ST_within(
            ST_Point(b.lon, b.lat), z.geometry
        ) as is_in_zone,
        b.battery_pct_0_100 >= 20 as is_trip_viable,

        (epoch(b.snapshot_ts) - epoch(b.last_reported)) > 3600 as is_stale,

        extract(hour from b.snapshot_ts at time zone 'Europe/Paris')          as hour_paris,
        extract(isodow from b.snapshot_ts at time zone 'Europe/Paris') in (6, 7) as is_weekend
    from bikes b
    cross join zone z
)
select * from enriched