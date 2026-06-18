{{ config(materialized='table') }}

with demand as (
    select h3_index, pop_total, demand_score
    from {{ ref('int_h3_demand_residential') }}
),

snapshots as (
    select distinct snapshot_ts
    from {{ ref('int_coverage_per_snapshot') }}
),

cell_snapshot_grid as (
    select d.h3_index, d.pop_total, d.demand_score, s.snapshot_ts
    from demand d
    cross join snapshots s
),

covered as (
    select
        g.h3_index,
        g.pop_total,
        g.demand_score,
        g.snapshot_ts,
        coalesce(c.is_covered_5min,  false) as is_covered_5min,
        coalesce(c.is_covered_10min, false) as is_covered_10min
    from cell_snapshot_grid g
    left join {{ ref('int_coverage_per_snapshot') }} c
      on g.h3_index = c.h3_cell
     and g.snapshot_ts = c.snapshot_ts
)

select
    snapshot_ts,

    sum(demand_score) filter (where is_covered_5min)
        / nullif(sum(demand_score), 0) * 100 as coverage_pct_weighted_5min,
    sum(demand_score) filter (where is_covered_10min)
        / nullif(sum(demand_score), 0) * 100 as coverage_pct_weighted_10min,

    sum(pop_total) filter (where is_covered_5min)
        / nullif(sum(pop_total), 0) * 100    as coverage_pct_unweighted_5min,
    sum(pop_total) filter (where is_covered_10min)
        / nullif(sum(pop_total), 0) * 100    as coverage_pct_unweighted_10min

from covered
group by snapshot_ts