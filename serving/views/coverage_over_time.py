import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from db import get_connection


@st.cache_data
def load_coverage() -> pd.DataFrame:
    with get_connection() as conn:
        df = conn.execute(
            """
            SELECT *
            FROM mart_coverage_per_snapshot
            ORDER BY snapshot_ts
        """
        ).df()
    df["snapshot_ts"] = pd.to_datetime(df["snapshot_ts"], utc=True)
    df["snapshot_ts"] = df["snapshot_ts"].dt.tz_convert("Europe/Paris")
    return df


def render():
    st.header("Coverage Over Time")

    st.caption(
        "How much of Parisian demand is within walking distance of a usable Dott bike, "
        "snapshot by snapshot — and is it trending up or down?"
    )

    df = load_coverage()

    max_ts = df["snapshot_ts"].max()

    fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
    with fcol1:
        window = st.selectbox(
            "Time window",
            ["All data", "Last 7 days", "Last 24 hours"],
            index=0,
            key="cov_window",
        )
    with fcol2:
        show_unweighted = st.checkbox(
            "Show unweighted (raw population)", value=False, key="cov_unweighted"
        )
    with fcol3:
        show_10min = st.checkbox("Show 10-min threshold", value=True, key="cov_10min")

    if window == "Last 24 hours":
        df_view = df[df["snapshot_ts"] >= max_ts - pd.Timedelta(hours=24)]
    elif window == "Last 7 days":
        df_view = df[df["snapshot_ts"] >= max_ts - pd.Timedelta(days=7)]
    else:
        df_view = df

    col1, col2, col3, col4 = st.columns(4)

    avg_w5 = df_view["coverage_pct_weighted_5min"].mean()
    avg_w10 = df_view["coverage_pct_weighted_10min"].mean()
    worst_w5_idx = df_view["coverage_pct_weighted_5min"].idxmin()
    worst_w5 = df_view.loc[worst_w5_idx, "coverage_pct_weighted_5min"]
    worst_w5_ts = df_view.loc[worst_w5_idx, "snapshot_ts"]

    col1.metric("Avg 5-min coverage", f"{avg_w5:.1f}%")
    col2.metric("Avg 10-min coverage", f"{avg_w10:.2f}%")
    col3.metric(
        "Worst 5-min snapshot",
        f"{worst_w5:.1f}%",
        help=f"At {worst_w5_ts:%Y-%m-%d %H:%M}",
    )
    col4.metric("Snapshots in window", f"{len(df_view):,}")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_view["snapshot_ts"],
            y=df_view["coverage_pct_weighted_5min"],
            name="Weighted 5-min",
            line=dict(color="#1f77b4", width=2),
        )
    )

    if show_10min:
        fig.add_trace(
            go.Scatter(
                x=df_view["snapshot_ts"],
                y=df_view["coverage_pct_weighted_10min"],
                name="Weighted 10-min",
                line=dict(color="#1f77b4", width=1, dash="dot"),
            )
        )

    if show_unweighted:
        fig.add_trace(
            go.Scatter(
                x=df_view["snapshot_ts"],
                y=df_view["coverage_pct_unweighted_5min"],
                name="Unweighted 5-min",
                line=dict(color="#ff7f0e", width=2),
            )
        )
        if show_10min:
            fig.add_trace(
                go.Scatter(
                    x=df_view["snapshot_ts"],
                    y=df_view["coverage_pct_unweighted_10min"],
                    name="Unweighted 10-min",
                    line=dict(color="#ff7f0e", width=1, dash="dot"),
                )
            )

    y_min = max(
        0,
        df_view[["coverage_pct_weighted_5min", "coverage_pct_weighted_10min"]]
        .min()
        .min()
        - 2,
    )

    fig.update_layout(
        xaxis_title="Snapshot time",
        yaxis_title="Coverage (%)",
        yaxis=dict(range=[y_min, 100.5]),
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", y=-0.15),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        **What this shows.** At every poll, we compute the share of Parisian demand
        within walking distance of a charged, in-zone Dott bike. The 5-minute line
        is the strict measure; the 10-minute line is the looser one.

        **The headline hides a spatial pattern.** Coverage stays around 97–99% at all
        times — but the dips correspond to ~25 peripheral cells temporarily losing
        coverage, mostly between 02:00 and 06:00. Their populations are small, so the
        percentage barely moves. The next page maps the spatial story this metric obscures.
        """
    )
