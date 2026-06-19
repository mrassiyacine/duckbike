import pandas as pd
import pydeck as pdk
import streamlit as st
from db import get_connection
from shapely import wkt


@st.cache_data
def load_road_usage() -> pd.DataFrame:
    con = get_connection()
    df = con.execute(
        """
        select name, length_m, n_trips, geometry_wkt
        from mart_road_usage
    """
    ).df()
    con.close()
    df["name"] = df["name"].fillna("(unnamed road)")
    return df


@st.cache_data
def load_trip_stats() -> dict:
    """Fleet-wide trip metrics from matched (origin→destination) trips.

    Only ``User Trip`` rows have a destination, so Operator Pickups — which carry
    a null ``end_time``/``dist_km`` — are excluded.
    """
    with get_connection() as con:
        df = con.execute(
            """
            select dist_km
            from mart_matched_trips
            where match_type = 'User Trip'
        """
        ).df()
    total_km = float(df["dist_km"].sum())
    return {
        "n_trips": len(df),
        "total_km": total_km,
        "co2_avoided_kg": total_km * CO2_AVOIDED_PER_KM_KG,
    }


# Per-km CO₂. A trip that replaces a car trip avoids the car's emissions but
# still incurs the e-bike's (charging + lifecycle). Net avoided = car − e-bike.
# ~120 g/km is a common European passenger-car figure; e-bike ≈ 10 g/km.
CO2_CAR_PER_KM_KG = 0.13
CO2_EBIKE_PER_KM_KG = 0.01
CO2_AVOIDED_PER_KM_KG = CO2_CAR_PER_KM_KG - CO2_EBIKE_PER_KM_KG


@st.cache_data
def build_heat_points(geom_tuple: tuple, trips_tuple: tuple) -> pd.DataFrame:
    """
    Sample the midpoint of every sub-segment of every linestring, weighted by
    n_trips. This turns road lines into a dense point cloud that HeatmapLayer
    can blur into the classic green→yellow→red glow.
    """
    rows = []
    for geom_wkt, weight in zip(geom_tuple, trips_tuple):
        coords = list(wkt.loads(geom_wkt).coords)
        w = float(weight)
        for i in range(len(coords) - 1):
            x0, y0 = coords[i]
            x1, y1 = coords[i + 1]
            rows.append({"lon": (x0 + x1) / 2, "lat": (y0 + y1) / 2, "weight": w})
    return pd.DataFrame(rows)


# Green → yellow → orange → red  (matches the reference image)
HEATMAP_COLORS = [
    [0, 255, 0, 255],
    [128, 255, 0, 255],
    [255, 255, 0, 255],
    [255, 160, 0, 255],
    [255, 80, 0, 255],
    [255, 0, 0, 255],
]

HEAT_RADIUS_PX = 8
HEAT_INTENSITY = 8
HEAT_THRESHOLD = 0.02


def render():
    st.header("Street Usage Last 7 days")
    st.caption(
        "Which streets does the fleet ride? Each detected trip is routed along the "
        "shortest bike path between its start and end; this shows how many trips use each street."
    )

    df = load_road_usage()

    with st.expander("Filters", expanded=False):
        fcol1, fcol2, fcol3 = st.columns([2, 2, 1])
        with fcol1:
            min_trips = st.slider(
                "Minimum trips on a street",
                min_value=10,
                max_value=int(df["n_trips"].quantile(0.99)),
                value=max(1, int(df["n_trips"].quantile(0.50))),
                help="Raise to hide quiet streets and reveal the main corridors.",
                key="ru_min_trips",
            )

    shown = df[df["n_trips"] >= min_trips].copy()
    if shown.empty:
        st.warning("No streets match the current filters.")
        st.stop()

    stats = load_trip_stats()
    c1, c2 = st.columns(2)
    c1.metric("Total distance ridden", f"{stats['total_km']:,.0f} km")
    c2.metric(
        "CO₂ avoided vs car",
        f"{stats['co2_avoided_kg']:,.0f} kg",
        help=(
            f"Assumes each of {stats['n_trips']:,} trips replaced a car trip of the "
            f"same distance. Net = car {CO2_CAR_PER_KM_KG * 1000:.0f} g − "
            f"e-bike {CO2_EBIKE_PER_KM_KG * 1000:.0f} g = "
            f"{CO2_AVOIDED_PER_KM_KG * 1000:.0f} g CO₂/km."
        ),
    )

    heat_df = build_heat_points(
        tuple(shown["geometry_wkt"]),
        tuple(shown["n_trips"]),
    )

    layer = pdk.Layer(
        "HeatmapLayer",
        data=heat_df,
        get_position=["lon", "lat"],
        get_weight="weight",
        radius_pixels=HEAT_RADIUS_PX,
        intensity=HEAT_INTENSITY,
        threshold=HEAT_THRESHOLD,
        color_range=HEATMAP_COLORS,
        aggregation="SUM",
    )
    st.markdown(
        """
        <div style="margin-top:12px;">
            <div style="display:flex; justify-content:space-between;
                        font-size:11px; margin-bottom:3px;">
                <span>Low</span><span>High</span>
            </div>
            <div style="height:14px; border-radius:4px;
                 background: linear-gradient(to right,
                     #00ff00, #80ff00, #ffff00, #ffa000, #ff5000, #ff0000);">
            </div>
            <div style="font-size:10px; color:#888; margin-top:4px;">
                trips per street segment
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(
                latitude=48.8566, longitude=2.3522, zoom=12, pitch=0
            ),
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        ),
        use_container_width=True,
    )

    with st.expander("Top 15 streets"):
        top = (
            df[df["name"] != "(unnamed road)"]
            .groupby("name", as_index=False)["n_trips"]
            .sum()
            .sort_values("n_trips", ascending=False)
            .head(15)
            .reset_index(drop=True)
        )
        st.bar_chart(top.set_index("name")["n_trips"])

    with st.expander("How street usage is computed — and its limits", expanded=True):
        st.markdown(
            """
Each **detected trip** is just two points: where a bike vanished (origin) and where one
reappeared (destination). We don't have the GPS trace, so we **infer the path**: the
shortest route along Paris' bike network between those two points. Counting how many
trips' paths cross each street gives this map.

**Key limitation — this is inferred, not measured.** Riders rarely take the literal
shortest path; they choose safer, flatter, or more familiar streets. So shortest-path
routing **over-weights main arteries** and **under-weights the quiet side streets**
cyclists actually prefer. Read it as *roughly where the demand corridors lie*, not a
precise GPS heatmap.
        """
        )
