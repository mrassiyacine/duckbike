import pandas as pd
import pydeck as pdk
import streamlit as st
from db import get_connection
from views._daytype import DAY_TYPES, slice_by_day_type


@st.cache_data
def load_od() -> pd.DataFrame:
    con = get_connection()
    df = con.execute(
        """
        select h3_index, hour_paris, is_weekend,
               avg_departures, avg_arrivals, avg_net_flow, n_observations
        from mart_od_density
    """
    ).df()
    con.close()
    return df


def scale_color(series: pd.Series, low: list, high: list, alpha: int = 200) -> list:
    """Linearly interpolate between low and high RGB based on normalised value."""
    vmin, vmax = series.min(), series.max()
    norm = ((series - vmin) / (vmax - vmin + 1e-9)).clip(0, 1)
    r = (low[0] + norm * (high[0] - low[0])).astype(int)
    g = (low[1] + norm * (high[1] - low[1])).astype(int)
    b = (low[2] + norm * (high[2] - low[2])).astype(int)
    return list(zip(r, g, b, [alpha] * len(series)))


def net_flow_color(series: pd.Series, alpha: int = 200) -> list:
    """Red for net origins, blue for net destinations, white at zero."""
    vmax = series.abs().max() + 1e-9
    norm = (series / vmax).clip(-1, 1)
    colors = []
    for v in norm:
        if v < 0:
            colors.append(
                [220, 50 + int((1 - abs(v)) * 180), 50 + int((1 - abs(v)) * 180), alpha]
            )
        else:
            colors.append(
                [50 + int((1 - v) * 180), 50 + int((1 - v) * 180), 220, alpha]
            )
    return colors


def render():
    st.header("Origin & Destination Density")
    st.caption(
        "Where do Dott trips start and end across Paris? "
        "Derived from bike counts: cells losing bikes = departures, cells gaining bikes = arrivals."
    )

    df = load_od()

    st.session_state.setdefault("od_hour", 8)
    play = st.toggle(
        "▶ Play hour animation",
        key="od_play",
        help="Auto-advance the hour every 0.5 s. Toggle off to scrub manually.",
    )

    @st.fragment(run_every=0.5 if play else None)
    def hour_view():
        if st.session_state.get("od_play"):
            st.session_state["od_hour"] = (st.session_state["od_hour"] + 1) % 24

        col_left, col_mid, col_right = st.columns([3, 1, 1])
        with col_left:
            hour = st.slider(
                "Hour of day (Paris time)",
                min_value=0,
                max_value=23,
                step=1,
                format="%02d:00",
                key="od_hour",
            )
        with col_mid:
            day_type = st.radio(
                "Day type", DAY_TYPES, horizontal=True, key="od_day_type"
            )
        with col_right:
            mode = st.radio(
                "Show",
                ["Departures", "Arrivals", "Net flow"],
                horizontal=True,
                key="od_mode",
            )

        df_day = slice_by_day_type(
            df,
            day_type,
            keys=["h3_index", "hour_paris"],
            weight_col="n_observations",
            weighted_cols=["avg_departures", "avg_arrivals", "avg_net_flow"],
            first_cols=[],
        )
        df_hour = df_day[df_day["hour_paris"] == hour].copy()
        df_hour["dep_label"] = df_hour["avg_departures"].round(2).astype(str)
        df_hour["arr_label"] = df_hour["avg_arrivals"].round(2).astype(str)
        df_hour["flow_label"] = df_hour["avg_net_flow"].round(2).astype(str)

        if mode == "Departures":
            df_hour["color"] = scale_color(
                df_hour["avg_departures"],
                low=[240, 240, 240],
                high=[220, 50, 50],
            )
            legend = "🔴 More departures (trip origins)"
        elif mode == "Arrivals":
            df_hour["color"] = scale_color(
                df_hour["avg_arrivals"],
                low=[240, 240, 240],
                high=[30, 100, 200],
            )
            legend = "🔵 More arrivals (trip destinations)"
        else:
            df_hour["color"] = net_flow_color(df_hour["avg_net_flow"])
            legend = "🔴 Net origin  · ⚪ Balanced  · 🔵 Net destination"

        total_dep = df_hour["avg_departures"].sum()
        total_arr = df_hour["avg_arrivals"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Avg departures at this hour", f"{total_dep:.0f}")
        c2.metric("Avg arrivals at this hour", f"{total_arr:.0f}")
        c3.metric(
            "Net imbalance",
            f"{abs(total_dep - total_arr):.0f}",
            help="Bikes that need rebalancing to restore equilibrium",
        )

        layer = pdk.Layer(
            "H3HexagonLayer",
            df_hour,
            pickable=True,
            filled=True,
            extruded=False,
            get_hexagon="h3_index",
            get_fill_color="color",
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
                        "<b>Departures:</b> {dep_label}/snapshot<br>"
                        "<b>Arrivals:</b> {arr_label}/snapshot<br>"
                        "<b>Net flow:</b> {flow_label}"
                    ),
                },
                map_style="light",
            ),
            use_container_width=True,
        )

        st.caption(legend)

    hour_view()

    with st.expander(
        "How origin & destination is computed — and its limits", expanded=True
    ):
        st.markdown(
            """
Every 10 minutes we count the bikes in each hexagon. Between two consecutive snapshots:

- A cell **losing** bikes → those bikes started a trip (**departure / origin**)
- A cell **gaining** bikes → trips ended there (**arrival / destination**)

**Filtering:** changes larger than ±8 bikes in a single 10-minute window are excluded —
those are rebalancing vans, not organic trips.

---

**Key limitation — we measure net flow, not gross flow.**

Within a 10-minute window, arrivals and departures can cancel each other out:

| 08:00 | 08:10 | Delta | What we record | What may have happened |
|-------|-------|-------|----------------|------------------------|
| 5 bikes | 5 bikes | 0 | nothing | 3 left, 3 arrived |
| 5 bikes | 7 bikes | +2 | 2 arrivals | 5 arrived, 3 left |

At busy cells, the departure and arrival counts shown here are **lower bounds** —
the true trip volume is higher. The figures are most accurate for quiet cells
and low-activity hours where simultaneous moves are rare.

**The net flow map remains valid**: a cell that consistently loses bikes at 8am
is a genuine origin zone regardless of how many simultaneous arrivals are hidden.
        """
        )
