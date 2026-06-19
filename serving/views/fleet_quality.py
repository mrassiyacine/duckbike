import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from db import get_connection
from views._daytype import DAY_TYPES


@st.cache_data
def load_theatrical() -> pd.DataFrame:
    with get_connection() as conn:
        df = conn.execute(
            """
            select
                snapshot_ts,
                hour_paris,
                is_weekend,
                n_reported,
                n_effective,
                n_theatrical,
                n_low_battery,
                n_out_of_zone,
                pct_theatrical
            from mart_theatrical_supply
            order by snapshot_ts
        """
        ).df()
    df["snapshot_ts"] = pd.to_datetime(df["snapshot_ts"], utc=True)
    return df


def render():
    st.header("Fleet Quality")
    st.caption(
        "Dott publishes a fleet size to the city. "
        "This page measures how many of those bikes are actually usable."
    )

    df = load_theatrical()

    day_type = st.radio(
        "Day type",
        DAY_TYPES,
        horizontal=True,
        key="fleet_day_type",
        help="Scopes the averages and the hour-of-day chart below.",
    )
    if day_type == "Weekday":
        df_day = df[~df["is_weekend"]]
    elif day_type == "Weekend":
        df_day = df[df["is_weekend"]]
    else:
        df_day = df

    avg_reported = int(df_day["n_reported"].mean())
    avg_effective = int(df_day["n_effective"].mean())
    avg_phantom = int(df_day["n_theatrical"].mean())
    avg_pct = df_day["pct_theatrical"].mean()
    avg_drained = int(df_day["n_low_battery"].mean())
    avg_ooz = int(df_day["n_out_of_zone"].mean())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Reported fleet (avg)", f"{avg_reported:,}")
    col2.metric(
        "Usable fleet (avg)",
        f"{avg_effective:,}",
        delta=f"-{avg_phantom:,} phantom",
        delta_color="inverse",
    )
    col3.metric("Phantom — low battery", f"{avg_drained:,}")
    col4.metric("Phantom — out of zone", f"{avg_ooz:,}")

    st.caption(
        f"On average **{avg_pct:.1f}%** of Dott's reported Paris fleet is unavailable to riders. "
        f"The vast majority ({avg_drained:,} bikes) are below 20% battery — still broadcast as available."
    )

    st.divider()

    st.subheader("Reported vs usable fleet over time")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["snapshot_ts"],
            y=df["n_reported"],
            mode="lines",
            name="Reported to city",
            line=dict(color="#9ecae1", width=1),
            fill="tozeroy",
            fillcolor="rgba(158,202,225,0.3)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["snapshot_ts"],
            y=df["n_effective"],
            mode="lines",
            name="Actually usable",
            line=dict(color="#2171b5", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(33,113,181,0.4)",
        )
    )
    fig.update_layout(
        xaxis_title="Time (Paris)",
        yaxis_title="Number of bikes",
        height=380,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("Phantom rate by hour of day")
    st.caption("When during the day is the gap largest?")

    hourly = df_day.groupby("hour_paris")["pct_theatrical"].mean().reset_index()

    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=hourly["hour_paris"],
            y=hourly["pct_theatrical"],
            marker_color=[
                "#d62728" if h in range(17, 23) else "#aec7e8"
                for h in hourly["hour_paris"]
            ],
            name="Phantom %",
        )
    )
    fig2.update_layout(
        xaxis=dict(title="Hour of day (Paris time)", dtick=1),
        yaxis=dict(title="Phantom fleet (%)", range=[0, 20]),
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="x",
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "The phantom rate peaks in the evening (17h–22h) when riders return bikes with depleted batteries "
        "faster than Dott can recharge and redeploy them."
    )

    with st.expander("How fleet quality is measured", expanded=True):
        st.markdown(
            """
**Step 1 — Every snapshot**, we read Dott's public GBFS feed and count every bike it
broadcasts to the city: the **reported fleet**.

**Step 2 — A bike counts as usable** only if it is **inside the operating zone** *and*
has **battery ≥ 20%**. Everything else is **phantom supply** — advertised as available
but not realistically rideable:
- **Low battery** — under 20% charge
- **Out of zone** — sitting outside Dott's service area

**Step 3 — Phantom rate** = phantom ÷ reported. The hourly chart averages it across all
days of the selected day type.

**Limitation:** we trust the feed's own battery and position. A bike could be unusable
for reasons the feed never reveals (mechanical faults, blocked parking), so these figures
are a **lower bound** on unusable supply.
        """
        )
