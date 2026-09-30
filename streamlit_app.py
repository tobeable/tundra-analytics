import streamlit as st

from src.ai_agent import show as ai_agent_show
from src.chart_agent import show as chart_agent_show
from src.dashboard import show as dashboard_show
from src.kpi_summary import show as kpi_summary_show
from src.semantic_search import show as semantic_search_show

st.set_page_config(
    page_title="Tundra Analytics",
    page_icon="\u2744",
    layout="wide",
)

_ROLE_PAGES = {
    "Analyst": [
        st.Page(dashboard_show, title="Dashboard", url_path="dashboard", default=True),
        st.Page(ai_agent_show, title="AI Agent", url_path="ai-agent"),
        st.Page(chart_agent_show, title="Charts", url_path="charts"),
        st.Page(semantic_search_show, title="Semantic Search", url_path="search"),
    ],
    "Manager": [
        st.Page(dashboard_show, title="Dashboard", url_path="dashboard", default=True),
        st.Page(ai_agent_show, title="AI Agent", url_path="ai-agent"),
        st.Page(chart_agent_show, title="Charts", url_path="charts"),
    ],
    "Executive": [
        st.Page(kpi_summary_show, title="Executive Summary", url_path="executive", default=True),
        st.Page(dashboard_show, title="Dashboard", url_path="dashboard"),
    ],
}

role = st.sidebar.selectbox("Role", list(_ROLE_PAGES.keys()))
pages = _ROLE_PAGES[role]

st.sidebar.divider()
if st.sidebar.button("Reset app"):
    st.cache_resource.clear()
    st.cache_data.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

nav = st.navigation(pages)
nav.run()
