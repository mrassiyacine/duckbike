{{ config(materialized='table') }}

with snapshots as (
    select distinct snapshot_ts
    from {{ ref('int_coverage_per_snapshot') }}
),

cell_snapshot_grid as (
    select
        d.h3_index,
        d.pop_total,
        d.demand_score,
        d.poverty_rate,
        s.snapshot_ts,
        extract(hour from s.snapshot_ts at time zone 'Europe/Paris')          as hour_paris,
        extract(isodow from s.snapshot_ts at time zone 'Europe/Paris') in (6, 7) as is_weekend
    from {{ ref('int_h3_demand_residential') }} d
    cross join snapshots s
),

covered as (
    select
        g.h3_index,
        g.pop_total,
        g.demand_score,
        g.poverty_rate,
        g.hour_paris,
        g.is_weekend,
        coalesce(c.is_covered_5min,  false) as is_covered_5min,
        coalesce(c.is_covered_10min, false) as is_covered_10min
    from cell_snapshot_grid g
    left join {{ ref('int_coverage_per_snapshot') }} c
      on g.h3_index    = c.h3_cell
     and g.snapshot_ts = c.snapshot_ts
)

select
    h3_index,
    hour_paris,
    is_weekend,
    any_value(pop_total)              as pop_total,
    any_value(demand_score)           as demand_score,
    any_value(poverty_rate)           as poverty_rate,
    avg(is_covered_5min::int)  * 100  as pct_covered_5min,
    avg(is_covered_10min::int) * 100  as pct_covered_10min,
    count(*)                          as n_snapshots
from covered
group by h3_index, hour_paris, is_weekend