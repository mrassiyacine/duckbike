from pathlib import Path

import streamlit as st
from views import (
    coverage_over_time,
    fleet_quality,
    od_density,
    road_usage,
    coverage_gaps,
)

st.set_page_config(
    page_title="DuckBike",
    page_icon="🚲",
    layout="wide",
)

LOGO_IMAGE = Path(__file__).parent / "assets" / "hero.png"

col_title, col_logo = st.columns([9, 1], vertical_alignment="center")
with col_title:
    st.title("Dott Paris — City Mobility Audit")
    st.caption("Independent analysis of Dott's bike-share fleet using raw GBFS data")
with col_logo:
    if LOGO_IMAGE.exists():
        st.image(str(LOGO_IMAGE))

TABS = {
    "Fleet Quality": fleet_quality,
    "Coverage Over Time": coverage_over_time,
    "Coverage Gaps": coverage_gaps,
    "Origin & Destination": od_density,
    "Street Usage": road_usage,
}

for tab, view in zip(st.tabs(list(TABS)), TABS.values()):
    with tab:
        view.render()
