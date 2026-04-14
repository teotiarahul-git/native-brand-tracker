"""
Shared UI components for the brand awareness dashboard.
KPI cards, filter sidebar, signal panels — reusable across categories.
"""

import streamlit as st


def kpi_card(label, value, delta=None, delta_color="normal"):
    """Render a KPI metric card."""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def render_kpi_row(metrics):
    """Render a row of KPI cards from a list of dicts."""
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            kpi_card(
                label=m.get("label", ""),
                value=m.get("value", "N/A"),
                delta=m.get("delta"),
                delta_color=m.get("delta_color", "normal"),
            )


def city_filter(geos, key="city_filter"):
    """Render a city filter dropdown in the sidebar."""
    geo_labels = ["All"] + [g.replace("_", " ").title() for g in geos]
    return st.sidebar.selectbox("City", geo_labels, key=key)


def date_range_filter(key="date_filter"):
    """Render a date range selector in the sidebar."""
    options = ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks", "All time"]
    return st.sidebar.selectbox("Time Range", options, key=key)


def comparison_set_filter(sets, key="set_filter"):
    """Render a comparison set toggle."""
    labels = list(sets.keys())
    display_labels = [sets[k].get("label", k) for k in labels]
    idx = st.sidebar.radio("Comparison Set", display_labels, key=key)
    return labels[display_labels.index(idx)]


def signal_panel(signals):
    """Render the watch-for signals panel."""
    if not signals:
        st.info("No active signals detected.")
        return

    for signal in signals:
        severity = signal.get("severity", "info")
        icon = {"warning": "⚠️", "positive": "✅", "info": "ℹ️"}.get(severity, "ℹ️")
        st.markdown(f"{icon} **{signal['title']}** — {signal['description']}")


def section_header(title, description=""):
    """Render a section header."""
    st.markdown(f"### {title}")
    if description:
        st.caption(description)


def empty_state(message="No data available yet. Run the data collection scripts first."):
    """Render an empty state message."""
    st.info(message)
