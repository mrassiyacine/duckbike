import pandas as pd
import pydeck as pdk
import streamlit as st
from db import get_connection
from views._daytype import DAY_TYPES, slice_by_day_type


@st.cache_data
def load_cell_coverage() -> pd.DataFrame:
    con = get_connection()
    df = con.execute(
        """
        select
            h3_index,
            hour_paris,
            is_weekend,
            pop_total,
            demand_score,
            pct_covered_5min,
            pct_covered_10min,
            n_snapshots
        from mart_cell_coverage
    """
    ).df()
    con.close()
    return df


def impact_color(df: pd.DataFrame) -> list:
    """Covered cells (>=95%) are near-invisible.
    Gap cells are colored light orange to deep red by impact score,
    where impact = demand_score x (100 - pct_covered_5min).
    """
    score = df["demand_score"] * (100 - df["pct_covered_5min"])
    gap_mask = df["pct_covered_5min"] < 95
    vmax = score[gap_mask].max() if gap_mask.any() else 1
    norm = (score / vmax).clip(0, 1)

    colors = []
    for is_gap, n in zip(gap_mask, norm):
        if not is_gap:
            colors.append([180, 180, 180, 25])
        else:
            r = 255
            g = int(200 - n * 170)
            b = int(50 - n * 40)
            a = int(120 + n * 135)
            colors.append([r, g, b, a])
    return colors


def render():
    st.header("Coverage Gaps")
    st.caption(
        "Which Paris neighbourhoods reliably have a usable Dott bike within walking distance — "
        "and which don't? Colour intensity combines coverage quality with how many potential "
        "riders live there: a poorly-covered cell with few residents stays faint."
    )

    df = load_cell_coverage()

    # ── animation control ─────────────────────────────────────────────────────
    # The toggle lives OUTSIDE the fragment: flipping it triggers a full rerun so
    # the fragment is re-created with a new run_every (the timer starts/stops).
    st.session_state.setdefault("gap_hour", 7)
    play = st.toggle(
        "▶ Play hour animation",
        key="gap_play",
        help="Auto-advance the hour every 0.5 s. Toggle off to scrub manually.",
    )

    @st.fragment(run_every=0.5 if play else None)
    def hour_view():

        if st.session_state.get("gap_play"):
            st.session_state["gap_hour"] = (st.session_state["gap_hour"] + 1) % 24

        col_slider, col_day = st.columns([3, 1])
        with col_slider:
            hour = st.slider(
                "Hour of day (Paris time)",
                min_value=0,
                max_value=23,
                step=1,
                format="%02d:00",
                key="gap_hour",
            )
        with col_day:
            day_type = st.radio(
                "Day type", DAY_TYPES, horizontal=True, key="gap_day_type"
            )

        df_day = slice_by_day_type(
            df,
            day_type,
            keys=["h3_index", "hour_paris"],
            weight_col="n_snapshots",
            weighted_cols=["pct_covered_5min", "pct_covered_10min"],
            first_cols=["pop_total", "demand_score"],
        )
        df_hour = df_day[df_day["hour_paris"] == hour].copy()
        df_hour["impact_score"] = (
            (df_hour["demand_score"] * (100 - df_hour["pct_covered_5min"]))
            .round(0)
            .astype(int)
        )
        df_hour["fill_color"] = impact_color(df_hour)
        df_hour["coverage_label"] = (
            df_hour["pct_covered_5min"].round(1).astype(str) + "%"
        )
        df_hour["pop_label"] = df_hour["pop_total"].round(0).astype(int)
        df_hour["demand_label"] = df_hour["demand_score"].round(0).astype(int)

        n_reliable = (df_hour["pct_covered_5min"] >= 95).sum()
        n_gap = (df_hour["pct_covered_5min"] < 95).sum()
        pop_in_gap = int(df_hour[df_hour["pct_covered_5min"] < 95]["pop_total"].sum())
        demand_lost = int(
            (df_hour["demand_score"] * (100 - df_hour["pct_covered_5min"]) / 100).sum()
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Reliable cells (≥95%)", f"{n_reliable:,}")
        col2.metric("Cells with gaps (<95%)", f"{n_gap:,}")
        col3.metric("Residents in gap cells", f"{pop_in_gap:,}")
        col4.metric(
            "Demand lost to gaps",
            f"{demand_lost:,}",
            help="Sum of demand_score × uncovered fraction across all gap cells — "
            "equivalent riders who can't reliably reach a bike at this hour",
        )

        layer = pdk.Layer(
            "H3HexagonLayer",
            df_hour,
            pickable=True,
            filled=True,
            extruded=False,
            get_hexagon="h3_index",
            get_fill_color="fill_color",
            line_width_min_pixels=0,
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=pdk.ViewState(
                    latitude=48.8566,
                    longitude=2.3522,
                    zoom=11,
                    pitch=0,
                ),
                tooltip={
                    "html": (
                        "<b>Coverage at {hour_paris}h:</b> {coverage_label}<br>"
                        "<b>Population:</b> {pop_label}<br>"
                        "<b>Demand score:</b> {demand_label}<br>"
                        "<b>Impact score:</b> {impact_score}"
                    ),
                },
                map_style="light",
            ),
            use_container_width=True,
        )

        st.caption(
            "⬜ Well covered (≥95%) — faded out  "
            "· 🟠 Gap — poor coverage, low demand  "
            "· 🔴 Critical gap — poor coverage AND many potential riders"
        )

    hour_view()

    with st.expander("How coverage is calculated", expanded=True):
        st.markdown(
            """
**Step 1 — Paris is divided into ~400 hexagons** (H3 resolution 9, ~0.1 km² each),
sourced from INSEE Filosofi census data. Only populated residential cells are included.

**Step 2 — Every 12 minutes**, we poll Dott's public GBFS feed and record every bike's
position, battery level, and last-reported timestamp.

**Step 3 — A bike is "usable"** if it meets all three conditions:
- Inside Dott's operating zone
- Battery ≥ 20%
- Reported within the last 30 minutes (not stale)

**Step 4 — Walk times** between every pair of hexagons are pre-computed from the
OpenStreetMap pedestrian network (not straight-line distance). A cell is **covered**
at a given snapshot if at least one usable bike is ≤ 5 minutes walk away.

**Step 5 — The % you see** is how often that cell was covered across all snapshots
recorded during that hour of day, over 20 days of data (May–June 2026).

**Step 6 — Colour encodes impact**, not just coverage quality:
`impact = demand_score × (100 − pct_covered_5min)`.
A cell at 40% coverage with 5,000 potential riders is shown much darker red than
a cell at 40% coverage with 50 residents.

A cell at 60% coverage at 07:00 means: on 4 out of 10 mornings at that hour,
no usable bike was within a 5-minute walk for residents of that neighbourhood.
        """
        )
