{{ config(materialized='table') }}

with aggregated as (
    select
        h3_index,

        sum(pop_total)      as pop_total,
        sum(pop_0_3)        as pop_0_3,
        sum(pop_4_5)        as pop_4_5,
        sum(pop_6_10)       as pop_6_10,
        sum(pop_11_17)      as pop_11_17,
        sum(pop_18_24)      as pop_18_24,
        sum(pop_25_39)      as pop_25_39,
        sum(pop_40_54)      as pop_40_54,
        sum(pop_55_64)      as pop_55_64,
        sum(pop_65_79)      as pop_65_79,
        sum(pop_80p)        as pop_80p,

        sum(households_total)                                                              as households_total,
        sum(households_poor)                                                               as households_poor,
        sum(standard_of_living_median * pop_total) / nullif(sum(pop_total), 0)            as standard_of_living_avg,
        sum(households_poor) / nullif(sum(households_total), 0)                           as poverty_rate,

        count(*)            as n_filosofi_cells

    from {{ ref('stg_filosofi') }}
    group by h3_index

)

select
    h3_index,

    pop_total,

    (
          (pop_0_3 + pop_4_5 + pop_6_10 + pop_11_17) * {{ var('demand_weight_0_17',  0.0) }}
        + pop_18_24 * {{ var('demand_weight_18_24', 1.0) }}
        + pop_25_39 * {{ var('demand_weight_25_39', 1.2) }}
        + pop_40_54 * {{ var('demand_weight_40_54', 0.9) }}
        + pop_55_64 * {{ var('demand_weight_55_64', 0.5) }}
        + pop_65_79 * {{ var('demand_weight_65_79', 0.2) }}
        + pop_80p   * {{ var('demand_weight_80p',   0.05) }}
    ) as demand_score,

    pop_0_3 + pop_4_5 + pop_6_10 + pop_11_17 as pop_minors,
    pop_18_24,
    pop_25_39,
    pop_40_54,
    pop_55_64,
    pop_65_79,
    pop_80p,

    households_poor,
    poverty_rate,
    standard_of_living_avg,

    n_filosofi_cells

from aggregated