"""Ads Measurement Console — entry point.

Internal-style Netflix ads measurement dashboard on a fully synthetic,
seeded DuckDB warehouse. See README.md for the tour.
"""

import streamlit as st

from src import auth, theme

st.set_page_config(
    page_title="Ads Measurement Console",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.register()

if not auth.require_login():
    st.stop()

# build the warehouse up front so every page loads instantly afterwards
from src import db  # noqa: E402
db.ensure_built()

pages = st.navigation([
    st.Page("app_pages/overview.py", title="Platform Overview", icon="📈", default=True),
    st.Page("app_pages/inventory.py", title="Inventory & Demand", icon="🎟️"),
    st.Page("app_pages/incrementality.py", title="Incrementality & Elasticity", icon="🧪"),
    st.Page("app_pages/ab_testing.py", title="A/B Testing", icon="⚖️"),
    st.Page("app_pages/recommendations.py", title="Recommendation Engine", icon="🧭"),
    st.Page("app_pages/agent.py", title="AI Analyst", icon="🤖"),
    st.Page("app_pages/cohort_console.py", title="Cohort Control Console", icon="🎚️"),
    st.Page("app_pages/data_model.py", title="Data Model & Methodology", icon="🗄️"),
])

with st.sidebar:
    st.markdown(
        "<div style='font-weight:800; font-size:1.15rem; color:#E50914;'>ADS MEASUREMENT</div>"
        "<div style='color:#898781; font-size:0.8rem; margin-bottom:0.5rem;'>internal console</div>",
        unsafe_allow_html=True)

pages.run()

with st.sidebar:
    st.divider()
    auth.logout_button()
    st.caption(
        "Built by **Andrew Skinner** — a working demo for the Ads Measurement "
        "Senior Analytics Engineer role. All data is synthetic (seeded simulation); "
        "no real Netflix, advertiser, or member data appears anywhere.")
