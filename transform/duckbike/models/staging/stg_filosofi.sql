{{ config(materialized='view') }}

select
    idcar_200m as cell_id,

    ind         as pop_total,
    ind_0_3     as pop_0_3,
    ind_4_5     as pop_4_5,
    ind_6_10    as pop_6_10,
    ind_11_17   as pop_11_17,
    ind_18_24   as pop_18_24,
    ind_25_39   as pop_25_39,
    ind_40_54   as pop_40_54,
    ind_55_64   as pop_55_64,
    ind_65_79   as pop_65_79,
    ind_80p     as pop_80p,

    men         as households_total,
    men_pauv    as households_poor,
    ind_snv     as standard_of_living_median,

    ST_GeomFromText(geometry) as geometry,
    h3_index
from {{ ref('filosofi_paris') }}