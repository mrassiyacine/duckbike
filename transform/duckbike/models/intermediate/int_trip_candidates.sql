{{ config(materialized='table') }}

with edges as (
    select
        o.sid as origin_id,
        d.sid as dest_id,

        o.bike_id  as origin_bike_id,
        o.last_seen as start_time,
        o.last_lat  as start_lat,
        o.last_lon  as start_lon,

        d.bike_id   as dest_bike_id,
        d.first_seen as end_time,
        d.first_lat  as end_lat,
        d.first_lon  as end_lon,

        -- haversine distance in km
        2 * 6371.0 * asin(sqrt(
            pow(sin(radians(d.first_lat - o.last_lat) / 2), 2)
            + cos(radians(o.last_lat)) * cos(radians(d.first_lat))
              * pow(sin(radians(d.first_lon - o.last_lon) / 2), 2)
        )) as dist_km,

        date_diff('second', o.last_seen, d.first_seen) / 3600.0 as time_diff_hours,
        o.last_battery - d.first_battery as batt_drop

    from {{ ref('int_recent_sessions') }} o
    join {{ ref('int_recent_sessions') }} d
      on  d.first_seen >  o.last_seen
      and d.first_seen <= o.last_seen + interval 1 hour * {{ var('trip_max_duration_hours') }}
      and o.last_battery - d.first_battery >= -{{ var('trip_battery_noise_tolerance') }}
      and d.first_lat between o.last_lat - {{ var('trip_max_distance_km') / 110.0 }}
                   and o.last_lat + {{ var('trip_max_distance_km') / 110.0 }}
      and d.first_lon between o.last_lon - {{ var('trip_max_distance_km') / 70.0 }}
                          and o.last_lon + {{ var('trip_max_distance_km') / 70.0 }}
),

scored as (
    select
        *,
        abs(batt_drop - dist_km * {{ var('trip_expected_batt_drop_per_km') }})
            + time_diff_hours * 60.0 * {{ var('trip_time_penalty_per_min') }}
            + {{ var('trip_distance_penalty_per_km') }} * dist_km as cost
    from edges
    where dist_km <= {{ var('trip_max_distance_km') }}
      and dist_km / time_diff_hours <= {{ var('trip_max_speed_kmh') }}
)

select
    origin_id,
    dest_id,
    origin_bike_id,
    start_time,
    start_lat,
    start_lon,
    dest_bike_id,
    end_time,
    end_lat,
    end_lon,
    dist_km,
    cost
from scored
where cost < {{ var('trip_dummy_penalty') }}
-- keep only the K cheapest destinations per origin
qualify row_number() over (partition by origin_id order by cost) <= {{ var('trip_top_k') }}
