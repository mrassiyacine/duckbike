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

st.title("Dott Paris — City Mobility Audit")
st.caption("Independent analysis of Dott's bike-share fleet using raw GBFS data")

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
