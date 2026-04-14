"""
Native (Water Purifiers) — Brand Awareness Dashboard
Native by Urban Company vs Aquaguard, Kent, Atomberg
"""

import streamlit as st
import pandas as pd
import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, PROJECT_ROOT)

from dashboard.utils.sheets_reader import (
    load_category_config, load_trends_data, load_volume_data, load_gsc_data,
    load_amazon_pi_data
)
from dashboard.utils.charts import (
    create_line_chart_from_section,
    create_volume_line_chart, create_volume_bar_chart,
    create_gsc_line_chart,
    create_amazon_pi_recall_chart, create_amazon_pi_recall_pct_chart,
    create_amazon_pi_sov_chart, create_amazon_pi_sov_simple_chart,
    create_amazon_pi_sov_vs_rank1_chart,
)
from dashboard.utils.components import empty_state

CATEGORY_ID = "native"

# Logos (Cloudinary / public)
UC_LOGO = "https://res.cloudinary.com/urbanclap/image/upload/t_high_res_category/images/supply/customer-app-supply/1648471968852-1f2b01.png"
NATIVE_LOGO = "https://res.cloudinary.com/urbanclap/image/upload/images/growth/home-screen/1756983018729-89d02c.jpeg"

# ================================================================ #
#  Page config
# ================================================================ #
st.set_page_config(
    page_title="Native — Brand Awareness Tracker",
    page_icon="💧",
    layout="wide",
)

# ================================================================ #
#  Global CSS — UC / Native brand identity
# ================================================================ #
st.markdown("""
<style>
/* ── Base ────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.stApp { background: #FAFAFA; }
section[data-testid="stSidebar"] { background: #FFF; border-right: 1px solid #E8E8E8; }

/* ── Header ──────────────────────────────────── */
.native-header {
    background: #212121;
    color: white;
    padding: 24px 32px;
    border-radius: 16px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
}
.native-header .left { display: flex; align-items: center; gap: 16px; }
.native-header .logo-mark {
    width: 44px; height: 44px; border-radius: 10px;
    background: #6E42E5; display: flex; align-items: center; justify-content: center;
    font-size: 1.4rem; font-weight: 700; color: white; letter-spacing: -0.03em;
    flex-shrink: 0;
}
.native-header h1 {
    font-size: 1.45rem; font-weight: 700; margin: 0; letter-spacing: -0.02em;
    line-height: 1.2;
}
.native-header .sub {
    font-size: 0.78rem; color: #BBBBBB; margin-top: 2px;
    display: flex; align-items: center; gap: 6px;
}
.native-header .sub img { height: 14px; opacity: 0.7; }
.native-header .right { display: flex; gap: 10px; }
.native-header .right a {
    color: #BBBBBB; font-size: 0.78rem; text-decoration: none;
    border: 1px solid #444; padding: 6px 14px; border-radius: 8px;
    transition: all 0.15s;
}
.native-header .right a:hover { color: white; border-color: #6E42E5; background: rgba(110,66,229,0.15); }

/* ── Executive Summary ───────────────────────── */
.exec-summary {
    background: #FFFFFF;
    border: 1px solid #E8E8E8;
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.exec-summary .summary-title {
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #8C8C8C; margin: 0 0 16px 0;
    display: flex; align-items: center; gap: 8px;
}
.exec-summary .summary-title::before {
    content: ''; display: inline-block; width: 3px; height: 14px;
    background: #6E42E5; border-radius: 2px;
}
.exec-row { display: flex; gap: 14px; flex-wrap: wrap; }
.exec-card {
    flex: 1; min-width: 200px;
    background: #FAFAFA; border: 1px solid #F0F0F0;
    border-radius: 12px; padding: 16px 18px;
    position: relative; overflow: hidden;
}
.exec-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: #E8E8E8; border-radius: 12px 12px 0 0;
}
.exec-card.up::before { background: #0F9D58; }
.exec-card.down::before { background: #DD0017; }
.exec-card .label {
    font-size: 0.68rem; font-weight: 600; color: #8C8C8C;
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;
}
.exec-card .value {
    font-size: 1.6rem; font-weight: 700; color: #212121;
    line-height: 1; letter-spacing: -0.02em;
}
.exec-card .delta {
    font-size: 0.82rem; font-weight: 600; margin-top: 6px;
    display: flex; align-items: center; gap: 3px;
}
.delta-up { color: #0F9D58; }
.delta-down { color: #DD0017; }
.delta-flat { color: #8C8C8C; }
.exec-card .context { font-size: 0.72rem; color: #BBBBBB; margin-top: 4px; }

/* ── Insight bar ─────────────────────────────── */
.insight-bar {
    border-radius: 10px; padding: 12px 18px; margin-top: 16px;
    font-size: 0.85rem; line-height: 1.6;
    display: flex; align-items: flex-start; gap: 10px;
}
.insight-bar .icon { font-size: 1rem; flex-shrink: 0; margin-top: 1px; }
.insight-bar.positive { background: #E6F4EA; color: #137333; }
.insight-bar.negative { background: #FDE7EA; color: #A50E0E; }
.insight-bar.neutral { background: #FFF8E1; color: #7A6400; }

/* ── Section labels ──────────────────────────── */
.source-label {
    font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.12em; color: #BBBBBB; margin-bottom: 4px;
    padding-left: 2px;
}

/* ── Tabs ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #E8E8E8; }
.stTabs [data-baseweb="tab"] {
    font-weight: 600; font-size: 0.88rem; padding: 10px 28px;
    color: #8C8C8C; border-bottom: 2px solid transparent; margin-bottom: -2px;
}
.stTabs [aria-selected="true"] { color: #212121; border-bottom-color: #6E42E5; }

/* ── Misc ────────────────────────────────────── */
.stExpander { border: 1px solid #E8E8E8; border-radius: 10px; }
hr { border-color: #F0F0F0; }
div[data-testid="stMetricValue"] { font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ================================================================ #
#  Header
# ================================================================ #
config = load_category_config(CATEGORY_ID)
sheet_url = config.get("google_sheet_url", "")
sheet_link = f'<a href="{sheet_url}" target="_blank">Google Sheet</a>' if sheet_url else ""

st.markdown(f"""
<div class="native-header">
    <div class="left">
        <div class="logo-mark">N</div>
        <div>
            <h1>Native — Brand Awareness Tracker</h1>
            <div class="sub">
                Water Purifiers &middot; Native vs Aquaguard, Kent, Atomberg &middot; All India
            </div>
        </div>
    </div>
    <div class="right">
        {sheet_link}
    </div>
</div>
""", unsafe_allow_html=True)


# ================================================================ #
#  Summary helpers
# ================================================================ #

def _delta(a, b):
    if a is None or b is None:
        return 0
    return a - b


def _delta_html(diff, suffix="pp"):
    if diff is None or diff == 0:
        return '<span class="delta delta-flat">--</span>'
    cls = "delta-up" if diff > 0 else "delta-down"
    arrow = "+" if diff > 0 else ""
    return f'<span class="delta {cls}">{arrow}{diff:.1f}{suffix}</span>'


def _card_cls(diff):
    if diff is None or diff == 0:
        return ""
    return "up" if diff > 0 else "down"


def _exec_card(label, value, delta_val=None, suffix="pp", context=""):
    cls = _card_cls(delta_val)
    d_html = _delta_html(delta_val, suffix) if delta_val is not None else ""
    ctx = f'<div class="context">{context}</div>' if context else ""
    return f"""
    <div class="exec-card {cls}">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {d_html}
        {ctx}
    </div>"""


def _last2(df, col):
    if df is None or df.empty or len(df) < 2 or col not in df.columns:
        return None, None
    v = pd.to_numeric(df[col], errors="coerce")
    return float(v.iloc[-1]), float(v.iloc[-2])


def build_weekly_summary(trends_data, pi_data):
    cards, insights = [], []

    avg_rows = trends_data.get("Competitor Share of Search (4-Week Average)", {}).get("rows", [])
    if len(avg_rows) >= 2:
        L, P = avg_rows[-1], avg_rows[-2]
        week = L.get("Week_Start", "")
        aq, aq_p = L.get("(%)Aqua (4wk avg)"), P.get("(%)Aqua (4wk avg)")
        kt, kt_p = L.get("(%)Kent (4wk avg)"), P.get("(%)Kent (4wk avg)")
        if aq is not None:
            cards.append(_exec_card("vs Aquaguard", f"{aq:.1f}%", _delta(aq, aq_p), context=f"Google Trends 4-wk avg &middot; {week}"))
        if kt is not None:
            cards.append(_exec_card("vs Kent", f"{kt:.1f}%", _delta(kt, kt_p), context=f"Google Trends 4-wk avg &middot; {week}"))

    rw = pi_data.get("brand_recall_weekly")
    if rw is not None and len(rw) >= 2:
        pc = [c for c in rw.columns if "%" in c or "vs" in c.lower()]
        if pc:
            now, prev = _last2(rw, pc[0])
            if now:
                cards.append(_exec_card("vs Competition", f"{now:.1f}%", _delta(now, prev), context="Amazon Brand Recall ratio"))

    sw = pi_data.get("ad_sov_weekly")
    if sw is not None and len(sw) >= 2:
        yb = [c for c in sw.columns if "Your Brand" in c]
        ca = [c for c in sw.columns if "Competitor Average" in c]
        if yb:
            now, prev = _last2(sw, yb[0])
            ca_now, _ = _last2(sw, ca[0]) if ca else (None, None)
            if now:
                ctx = f"Amazon Ad SoV &middot; Comp avg {ca_now:.1f}%" if ca_now else "Amazon Ad SoV"
                cards.append(_exec_card("Ad Share of Voice", f"{now:.1f}%", _delta(now, prev), context=ctx))

    if len(avg_rows) >= 5:
        aq_4w = avg_rows[-4].get("(%)Aqua (4wk avg)", 0)
        aq_now = avg_rows[-1].get("(%)Aqua (4wk avg)", 0)
        if aq_now and aq_4w:
            tr = aq_now - aq_4w
            if abs(tr) >= 1:
                verb = "gained" if tr > 0 else "lost"
                cls = "positive" if tr > 0 else "negative"
                icon = "arrow_upward" if tr > 0 else "arrow_downward"
                insights.append((cls, f"Native has <b>{verb} {abs(tr):.1f}pp</b> against Aquaguard on Google search over the past 4 weeks."))

    return cards, insights


def build_monthly_summary(volume_data, pi_data):
    cards, insights = [], []

    pct_rows = volume_data.get("Native as % of Competitors (Monthly)", {}).get("rows", [])
    if len(pct_rows) >= 2:
        L, P = pct_rows[-1], pct_rows[-2]
        mo = L.get("Month", "")
        aq, aq_p = L.get("(%)Aqua (Monthly)"), P.get("(%)Aqua (Monthly)")
        kt, kt_p = L.get("(%)Kent (Monthly)"), P.get("(%)Kent (Monthly)")
        if aq is not None:
            cards.append(_exec_card("vs Aquaguard", f"{aq:.1f}%", _delta(aq, aq_p), context=f"Google Ads Keyword Planner &middot; {mo}"))
        if kt is not None:
            cards.append(_exec_card("vs Kent", f"{kt:.1f}%", _delta(kt, kt_p), context=f"Google Ads Keyword Planner &middot; {mo}"))

    vol_s = volume_data.get("Brand Total Volume", {})
    vol_rows = vol_s.get("rows", [])
    if len(vol_rows) >= 2:
        nc = [h for h in vol_s.get("headers", []) if "Native" in h]
        if nc:
            nv = vol_rows[-1].get(nc[0], 0)
            pv = vol_rows[-2].get(nc[0], 0)
            pch = ((nv - pv) / pv * 100) if pv else 0
            cards.append(_exec_card("Native Branded Searches", f"{nv:,}", pch, suffix="%", context="Google Ads Keyword Planner"))

    rm = pi_data.get("brand_recall_monthly")
    if rm is not None and len(rm) >= 2:
        pc = [c for c in rm.columns if "%" in c or "vs" in c.lower()]
        if pc:
            now, prev = _last2(rm, pc[0])
            if now:
                cards.append(_exec_card("vs Competition", f"{now:.1f}%", _delta(now, prev), context="Amazon Brand Recall ratio"))

    sm = pi_data.get("ad_sov_monthly")
    if sm is not None and len(sm) >= 2:
        yb = [c for c in sm.columns if "Your Brand" in c]
        r1 = [c for c in sm.columns if "Rank 1" in c]
        if yb:
            now, prev = _last2(sm, yb[0])
            r1_now = None
            if r1:
                r1_now, _ = _last2(sm, r1[0])
            ctx = f"Amazon Ad SoV &middot; {(now/r1_now*100):.0f}% of {r1[0]}" if r1_now and r1_now > 0 else "Amazon Ad SoV"
            if now:
                cards.append(_exec_card("Ad Share of Voice", f"{now:.1f}%", _delta(now, prev), context=ctx))

    if len(pct_rows) >= 4:
        aq3 = pct_rows[-3].get("(%)Aqua (Monthly)", 0)
        aq_now = pct_rows[-1].get("(%)Aqua (Monthly)", 0)
        if aq_now and aq3:
            tr = aq_now - aq3
            if abs(tr) >= 1:
                verb = "gained" if tr > 0 else "lost"
                cls = "positive" if tr > 0 else "negative"
                insights.append((cls, f"3-month trend: Native has <b>{verb} {abs(tr):.1f}pp</b> against Aquaguard on branded search volume."))

    return cards, insights


def render_exec_summary(cards, insights, period_label=""):
    if not cards:
        return
    cards_html = "\n".join(cards)
    insights_html = ""
    for cls, text in insights:
        icon = "&#9650;" if cls == "positive" else "&#9660;" if cls == "negative" else "&#9644;"
        insights_html += f'<div class="insight-bar {cls}"><span class="icon">{icon}</span><span>{text}</span></div>\n'

    st.markdown(f"""
    <div class="exec-summary">
        <div class="summary-title">Executive Summary &mdash; {period_label}</div>
        <div class="exec-row">{cards_html}</div>
        {insights_html}
    </div>
    """, unsafe_allow_html=True)


def source_label(text):
    st.markdown(f'<div class="source-label">{text}</div>', unsafe_allow_html=True)


# ================================================================ #
#  TABS
# ================================================================ #
tab_weekly, tab_monthly = st.tabs(["Weekly", "Monthly"])

# ================================================================ #
#  WEEKLY
# ================================================================ #
with tab_weekly:
    trends_data = load_trends_data(CATEGORY_ID)
    pi_data = load_amazon_pi_data(CATEGORY_ID)

    cards, insights = build_weekly_summary(trends_data, pi_data)
    render_exec_summary(cards, insights, "Weekly")

    if trends_data:
        avg_key = "Competitor Share of Search (4-Week Average)"
        if avg_key in trends_data:
            source_label("GOOGLE TRENDS")
            fig = create_line_chart_from_section(
                trends_data[avg_key], CATEGORY_ID,
                title="Native searches as % of each competitor",
                subtitle="4-week rolling average. Higher = Native is closing the awareness gap. Dotted lines mark major campaigns.",
                date_key="Week_Start", y_title="Native as % of Competitor",
                tick_suffix="%", hidden_traces=["Atomberg"],
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="w_4wk")

        fm_key = "Share of Search — Full Market"
        if fm_key in trends_data:
            fig = create_line_chart_from_section(
                trends_data[fm_key], CATEGORY_ID,
                title="Share of Search — Full Market",
                subtitle="Each brand's share of total branded search interest. All brands sum to ~100%.",
                date_key="Week_Start", y_title="Share of Search (%)",
                tick_suffix="%",
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="w_fm")
    else:
        empty_state("Google Trends data not available.")

    st.divider()

    recall_w = pi_data.get("brand_recall_weekly")
    sov_w = pi_data.get("ad_sov_weekly")

    if recall_w is not None and not recall_w.empty:
        source_label("AMAZON PRODUCT INTELLIGENCE")
        fig = create_amazon_pi_recall_pct_chart(
            recall_w,
            title="Native search (%) vs Competitor average",
            subtitle="Ratio of Native to competitor indexed searches on Amazon. Baseline-independent.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="w_rc_pct")

        fig = create_amazon_pi_recall_chart(
            recall_w,
            title="Indexed Brand Recall — Native vs Competitors",
            subtitle="Rebased search index on Amazon. Higher = more shoppers searching for the brand.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="w_rc_idx")

        with st.expander("View raw data — Brand Recall (Weekly)"):
            st.dataframe(recall_w, use_container_width=True, hide_index=True)

    if sov_w is not None and not sov_w.empty:
        fig = create_amazon_pi_sov_simple_chart(
            sov_w,
            title="Ad Share of Voice — Native vs Competition",
            subtitle="First-page sponsored product impression share. Purple fill = Native's lead over competitor average.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="w_sov")

        with st.expander("View raw data — Ad SoV (Weekly)"):
            st.dataframe(sov_w, use_container_width=True, hide_index=True)


# ================================================================ #
#  MONTHLY
# ================================================================ #
with tab_monthly:
    volume_data = load_volume_data(CATEGORY_ID)
    pi_data = load_amazon_pi_data(CATEGORY_ID)

    cards, insights = build_monthly_summary(volume_data, pi_data)
    render_exec_summary(cards, insights, "Monthly")

    if volume_data:
        pct_key = "Native as % of Competitors (Monthly)"
        if pct_key in volume_data:
            source_label("GOOGLE ADS KEYWORD PLANNER")
            fig = create_line_chart_from_section(
                volume_data[pct_key], CATEGORY_ID,
                title="Native searches as % of each competitor",
                subtitle="Monthly branded search volume ratio. Steady rise = growing relative awareness.",
                date_key="Month", y_title="Native as % of Competitor",
                tick_suffix="%",
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="m_pct")

        vol_key = "Brand Total Volume"
        if vol_key in volume_data:
            fig = create_volume_line_chart(
                volume_data[vol_key], CATEGORY_ID,
                title="Monthly Branded Search Volume — All Players",
                subtitle="Total Google searches per brand. Shows absolute awareness size and seasonal patterns.",
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="m_vol")
    else:
        empty_state("Monthly search volume data not available.")

    st.divider()

    recall_m = pi_data.get("brand_recall_monthly")
    sov_m = pi_data.get("ad_sov_monthly")

    if recall_m is not None and not recall_m.empty:
        source_label("AMAZON PRODUCT INTELLIGENCE")
        fig = create_amazon_pi_recall_pct_chart(
            recall_m,
            title="Native search (%) vs Competitor average",
            subtitle="24-month view. Ratio of Native to competitor indexed searches on Amazon.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="m_rc_pct")

        fig = create_amazon_pi_recall_chart(
            recall_m,
            title="Indexed Brand Recall — Native vs Competitors",
            subtitle="Rebased index across multiple Pi extractions. Both lines on the same scale.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="m_rc_idx")

        with st.expander("View raw data — Brand Recall (Monthly)"):
            st.dataframe(recall_m, use_container_width=True, hide_index=True)

    if sov_m is not None and not sov_m.empty:
        fig = create_amazon_pi_sov_chart(
            sov_m,
            title="Advertising Share of Voice — All Players",
            subtitle="First-page sponsored product impression share. Includes top 3 ranked competitors from Amazon Pi.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="m_sov")

        fig = create_amazon_pi_sov_vs_rank1_chart(
            sov_m,
            title="Native Ad SoV as % of Rank 1 Brand",
            subtitle="How close Native's ad presence is to the category leader. Crossing 100% = outperforming Rank 1.",
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="m_sov_r1")

        with st.expander("View raw data — Ad SoV (Monthly)"):
            st.dataframe(sov_m, use_container_width=True, hide_index=True)
