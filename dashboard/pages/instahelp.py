"""
InstaHelp (House Help) — Brand Awareness Dashboard
Tracks InstaHelp vs Snabbit and Pronto across India + 7 cities.
"""

import streamlit as st
import pandas as pd
import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, PROJECT_ROOT)

from dashboard.utils.sheets_reader import (
    load_category_config, load_trends_data, load_volume_data, load_gsc_data
)
from dashboard.utils.charts import (
    create_trends_line_chart, create_volume_bar_chart,
    create_gsc_line_chart, create_city_heatmap
)
from dashboard.utils.components import (
    render_kpi_row, city_filter, date_range_filter,
    section_header, empty_state, signal_panel
)

CATEGORY_ID = "instahelp"

st.set_page_config(
    page_title="InstaHelp — Brand Awareness",
    page_icon="🏠",
    layout="wide",
)

# Header
st.markdown("## InstaHelp (House Help) — Brand Awareness Dashboard")
st.caption("InstaHelp by Urban Company vs Snabbit, Pronto · India + 7 Cities")

# Load config
config = load_category_config(CATEGORY_ID)
geos = config.get("geos", ["india"])

# Sidebar filters
st.sidebar.markdown("### Filters")
selected_city = city_filter(geos, key="ih_city")
selected_range = date_range_filter(key="ih_range")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview",
    "Google Trends (Weekly)",
    "Monthly Search Volume (Google Ads)",
    "Google Search Console (Weekly)"
])

# ============ TAB 1: Overview ============
with tab1:
    trends_data = load_trends_data(CATEGORY_ID)
    volume_data = load_volume_data(CATEGORY_ID)
    gsc_data = load_gsc_data(CATEGORY_ID)

    if not trends_data and volume_data == {} and gsc_data.empty:
        empty_state("No data collected yet. Run `/instahelp-tracker run` to collect data.")
    else:
        # KPI cards from latest trends
        section_header("Latest Indexed Searches", "Google Trends — relative search interest (0-100)")
        if trends_data:
            # Get first section's latest data
            first_section = list(trends_data.values())[0] if trends_data else None
            if first_section and first_section.get("rows"):
                latest = first_section["rows"][-1]
                headers = [h for h in first_section["headers"] if h not in ("Week_Start", "Notes")]
                metrics = []
                for h in headers:
                    val = latest.get(h, 0)
                    metrics.append({"label": h, "value": str(val)})
                if metrics:
                    render_kpi_row(metrics)
                st.caption(f"Week of {latest.get('Week_Start', 'N/A')}")
        else:
            empty_state("Google Trends data not yet collected.")

        st.markdown("---")

        # Trends chart (first section)
        if trends_data:
            first_key = list(trends_data.keys())[0]
            fig = create_trends_line_chart(trends_data[first_key], CATEGORY_ID, title=first_key)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        # City heatmap
        if len(trends_data) > 1:
            section_header("City Comparison", "Latest indexed searches across cities")
            city_df = create_city_heatmap(trends_data, CATEGORY_ID)
            if city_df is not None:
                st.dataframe(city_df, use_container_width=True, hide_index=True)

        # Volume summary
        if volume_data:
            section_header("Latest Monthly Search Volumes", "Google Ads Keyword Planner")
            first_vol_key = list(volume_data.keys())[0]
            fig_vol = create_volume_bar_chart(volume_data[first_vol_key], CATEGORY_ID, title=first_vol_key)
            if fig_vol:
                st.plotly_chart(fig_vol, use_container_width=True)

    # Sheet link
    if config.get("google_sheet_url"):
        st.markdown(f"[Open Full Google Sheet]({config['google_sheet_url']})")

# ============ TAB 2: Google Trends ============
with tab2:
    trends_data = load_trends_data(CATEGORY_ID)

    if not trends_data:
        empty_state("Google Trends data not yet collected. Run `/instahelp-tracker trends`.")
    else:
        # Let user pick which section to view
        section_names = list(trends_data.keys())
        if section_names:
            selected_section = st.selectbox("Select comparison view and city", section_names)
            section = trends_data[selected_section]

            fig = create_trends_line_chart(section, CATEGORY_ID, title=selected_section)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            # Data table
            if section.get("rows"):
                with st.expander("View raw data"):
                    df = pd.DataFrame(section["rows"])
                    st.dataframe(df, use_container_width=True, hide_index=True)

# ============ TAB 3: Monthly Search Volume ============
with tab3:
    volume_data = load_volume_data(CATEGORY_ID)

    if not volume_data:
        empty_state("Monthly search volume data not yet collected. Run `/instahelp-tracker volume`.")
    else:
        section_names = list(volume_data.keys())
        if section_names:
            selected_section = st.selectbox("Select city", section_names, key="vol_section")
            section = volume_data[selected_section]

            fig = create_volume_bar_chart(section, CATEGORY_ID, title=selected_section)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            # Volume trend over time
            if section.get("rows") and len(section["rows"]) > 1:
                section_header("Volume Trends Over Time")
                df = pd.DataFrame(section["rows"])
                vol_cols = [c for c in df.columns if "Volume" in c]
                if vol_cols:
                    import plotly.graph_objects as go
                    fig2 = go.Figure()
                    from dashboard.utils.theme import get_category_palette
                    palette = get_category_palette(CATEGORY_ID)
                    for col in vol_cols:
                        brand = col.replace(" Volume", "")
                        color = palette.get(brand, "#8C8C8C")
                        fig2.add_trace(go.Scatter(
                            x=df["Month"], y=pd.to_numeric(df[col], errors="coerce"),
                            mode="lines+markers", name=brand,
                            line=dict(color=color, width=2),
                        ))
                    fig2.update_layout(
                        title="Monthly Search Volume Trends",
                        xaxis_title="Month", yaxis_title="Search Volume",
                        template="plotly_white", height=400,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            with st.expander("View raw data"):
                df = pd.DataFrame(section["rows"])
                st.dataframe(df, use_container_width=True, hide_index=True)

# ============ TAB 4: Google Search Console ============
with tab4:
    gsc_df = load_gsc_data(CATEGORY_ID)

    if gsc_df.empty:
        empty_state("Google Search Console data not yet collected. Run `/instahelp-tracker gsc`.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            fig_imp = create_gsc_line_chart(
                gsc_df, "Total Branded Impressions",
                title="Branded Impressions (Weekly)", color="#4A90D9"
            )
            if fig_imp:
                st.plotly_chart(fig_imp, use_container_width=True)

        with col2:
            fig_clicks = create_gsc_line_chart(
                gsc_df, "Total Branded Clicks",
                title="Branded Clicks (Weekly)", color="#27AE60"
            )
            if fig_clicks:
                st.plotly_chart(fig_clicks, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            fig_ctr = create_gsc_line_chart(
                gsc_df, "Click-Through Rate %",
                title="Click-Through Rate % (Weekly)", color="#F39C12"
            )
            if fig_ctr:
                st.plotly_chart(fig_ctr, use_container_width=True)

        with col4:
            fig_pos = create_gsc_line_chart(
                gsc_df, "Avg Position",
                title="Average Position (Weekly)", color="#E74C3C"
            )
            if fig_pos:
                st.plotly_chart(fig_pos, use_container_width=True)

        with st.expander("View raw data"):
            st.dataframe(gsc_df, use_container_width=True, hide_index=True)
