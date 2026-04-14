"""
Plotly chart builders for the brand awareness dashboard.
Professional, self-explanatory charts with event annotations.
"""

import plotly.graph_objects as go
import pandas as pd
from .theme import (
    get_category_palette, PLOTLY_LAYOUT, EVENTS,
    NATIVE_PURPLE, AQUA_BLUE, KENT_GREEN, COMP_AVG_SLATE,
    UC_GRAY_200, UC_GRAY_400, UC_GRAY_500, UC_GRAY_800, UC_WHITE, UC_BLACK,
)


def _base_layout(**overrides):
    """Merge base plotly layout with per-chart overrides."""
    layout = {**PLOTLY_LAYOUT}
    for k, v in overrides.items():
        if isinstance(v, dict) and k in layout and isinstance(layout[k], dict):
            layout[k] = {**layout[k], **v}
        else:
            layout[k] = v
    return layout


def _add_events(fig, date_key="Week_Start", df=None):
    """Add vertical event annotation lines to a chart."""
    if df is None or df.empty:
        return

    # Determine date range in the chart
    dates = pd.to_datetime(df[date_key], errors="coerce")
    min_date, max_date = dates.min(), dates.max()

    for ev in EVENTS:
        # Pick the right date granularity
        if date_key == "Month":
            ev_date = pd.Timestamp(ev["month"] + "-15")
        elif date_key == "Week_Start":
            ev_date = pd.Timestamp(ev.get("week", ev["date"]))
        else:
            ev_date = pd.Timestamp(ev["date"])

        if pd.isna(min_date) or pd.isna(max_date):
            continue
        if ev_date < min_date or ev_date > max_date:
            continue

        # Use the actual x-axis value (string) for placement
        if date_key == "Month":
            x_val = ev["month"]
        elif date_key == "Week_Start":
            x_val = ev.get("week", ev["date"])
        else:
            x_val = ev["date"]

        fig.add_vline(
            x=x_val, line_width=1.5, line_dash="dot",
            line_color=ev["color"], opacity=0.7,
        )
        fig.add_annotation(
            x=x_val, y=1.0, yref="paper",
            text=ev["label"], showarrow=False,
            font=dict(size=9, color=ev["color"]),
            textangle=-90, xanchor="left", yanchor="top",
            xshift=4,
        )


def _title_html(title, subtitle=""):
    if subtitle:
        return f"<b>{title}</b><br><span style='font-size:11px;color:#8C8C8C'>{subtitle}</span>"
    return f"<b>{title}</b>"


# ------------------------------------------------------------------ #
#  Generic line chart from section data
# ------------------------------------------------------------------ #

def create_line_chart_from_section(section_data, category_id, title="",
                                   date_key="Week_Start", y_title="",
                                   tick_suffix="", height=420,
                                   hidden_traces=None, subtitle=""):
    if not section_data or not section_data.get("rows"):
        return None

    rows = section_data["rows"]
    headers = [h for h in section_data["headers"]
               if h not in (date_key, "Notes")]

    df = pd.DataFrame(rows)
    if date_key not in df.columns:
        return None

    palette = get_category_palette(category_id)
    hidden_traces = hidden_traces or []

    fig = go.Figure()
    for col in headers:
        if col in df.columns:
            color = palette.get(col, UC_GRAY_500)
            vis = "legendonly" if any(h.lower() in col.lower() for h in hidden_traces) else True
            fig.add_trace(go.Scatter(
                x=df[date_key], y=df[col],
                mode="lines", name=col,
                line=dict(color=color, width=2.5, shape="spline"),
                visible=vis,
                hovertemplate=f"<b>{col}</b><br>%{{x}}<br>%{{y:.1f}}{tick_suffix}<extra></extra>",
            ))

    _add_events(fig, date_key, df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=height,
        yaxis=dict(title=y_title, ticksuffix=tick_suffix),
    ))
    return fig


# ------------------------------------------------------------------ #
#  Google Trends
# ------------------------------------------------------------------ #

def create_trends_line_chart(section_data, category_id, title=""):
    return create_line_chart_from_section(
        section_data, category_id, title=title,
        date_key="Week_Start", y_title="Indexed Searches (0-100)",
    )


# ------------------------------------------------------------------ #
#  Monthly Volume
# ------------------------------------------------------------------ #

def create_volume_line_chart(section_data, category_id, title="", subtitle=""):
    if not section_data or not section_data.get("rows"):
        return None

    rows = section_data["rows"]
    headers = [h for h in section_data["headers"]
               if h not in ("Month", "Notes", "Total Market")]

    df = pd.DataFrame(rows)
    if "Month" not in df.columns:
        return None

    palette = get_category_palette(category_id)

    fig = go.Figure()
    for col in headers:
        if col not in df.columns:
            continue
        display = col.replace(" Volume", "").replace(" Total", "").strip()
        color = palette.get(col, palette.get(display, UC_GRAY_500))
        fig.add_trace(go.Scatter(
            x=df["Month"], y=df[col],
            mode="lines+markers", name=display,
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=4),
            hovertemplate=f"<b>{display}</b><br>%{{x}}<br>%{{y:,.0f}}<extra></extra>",
        ))

    _add_events(fig, "Month", df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=420,
        yaxis=dict(title="Monthly Search Volume"),
    ))
    return fig


def create_volume_bar_chart(section_data, category_id, title=""):
    if not section_data or not section_data.get("rows"):
        return None

    rows = section_data["rows"]
    headers = [h for h in section_data["headers"]
               if h not in ("Month", "Notes", "Total Market")]
    if not rows:
        return None

    latest = rows[-1]
    palette = get_category_palette(category_id)

    brands, volumes, colors = [], [], []
    for h in headers:
        if h not in latest:
            continue
        if "Volume" in h or "Total" in h:
            brand_name = h.replace(" Volume", "").replace(" Total", "").strip()
            if not brand_name:
                brand_name = h
            brands.append(brand_name)
            volumes.append(latest.get(h, 0))
            colors.append(palette.get(brand_name, palette.get(h, UC_GRAY_500)))

    if not brands:
        return None

    fig = go.Figure(data=[go.Bar(
        x=brands, y=volumes, marker_color=colors,
        text=[f"{v:,}" for v in volumes], textposition="outside",
    )])
    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(f"{title} ({latest.get('Month', '')})")),
        height=400, yaxis=dict(title="Monthly Search Volume"),
    ))
    return fig


# ------------------------------------------------------------------ #
#  GSC
# ------------------------------------------------------------------ #

def create_gsc_line_chart(df, metric_col, title="", color=NATIVE_PURPLE):
    if df.empty or metric_col not in df.columns:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Week_Start"], y=pd.to_numeric(df[metric_col], errors="coerce"),
        mode="lines", name=metric_col,
        line=dict(color=color, width=2.5, shape="spline"),
    ))
    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title)),
        height=350, yaxis=dict(title=metric_col),
    ))
    return fig


# ------------------------------------------------------------------ #
#  Amazon Pi — Brand Recall
# ------------------------------------------------------------------ #

def create_amazon_pi_recall_chart(df, title="", subtitle=""):
    """Dual-line — Native vs Competitor Average (rebased index)."""
    if df.empty:
        return None

    date_col = df.columns[0]
    brand_col = [c for c in df.columns if "Rebased Index" in c or "Your Brand" in c]
    comp_col = [c for c in df.columns if "Competitor" in c]
    if not brand_col or not comp_col:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[brand_col[0]],
        mode="lines+markers", name="Native",
        line=dict(color=NATIVE_PURPLE, width=3, shape="spline"),
        marker=dict(size=5, color=NATIVE_PURPLE),
        hovertemplate="<b>Native</b><br>%{x}<br>Index: %{y:.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[comp_col[0]],
        mode="lines+markers", name="Competitor Average",
        line=dict(color=COMP_AVG_SLATE, width=2.5, shape="spline"),
        marker=dict(size=4, color=COMP_AVG_SLATE),
        hovertemplate="<b>Competitor Avg</b><br>%{x}<br>Index: %{y:.0f}<extra></extra>",
    ))

    _add_events(fig, date_col, df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=400, yaxis=dict(title="Indexed Searches (Rebased)"),
    ))
    return fig


def create_amazon_pi_recall_pct_chart(df, title="", subtitle=""):
    """Area chart — Native as % of Competitor Average."""
    if df.empty:
        return None

    date_col = df.columns[0]
    pct_col = [c for c in df.columns if "%" in c or "vs" in c.lower()]
    if not pct_col:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[pct_col[0]],
        mode="lines+markers",
        name="Native as % of Competitor Average",
        line=dict(color=NATIVE_PURPLE, width=3, shape="spline"),
        marker=dict(size=6, color=NATIVE_PURPLE),
        fill="tozeroy",
        fillcolor="rgba(110, 66, 229, 0.06)",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
    ))

    _add_events(fig, date_col, df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=360, yaxis=dict(title="Native as % of Competitor Average", ticksuffix="%"),
    ))
    return fig


# ------------------------------------------------------------------ #
#  Amazon Pi — Ad Share of Voice
# ------------------------------------------------------------------ #

def create_amazon_pi_sov_chart(df, title="", subtitle=""):
    """Grouped bar — all columns (Native, Comp Avg, Ranks)."""
    if df.empty:
        return None

    date_col = df.columns[0]
    value_cols = [c for c in df.columns if c not in (date_col, "Delta", "Notes", "")]
    if not value_cols:
        return None

    color_map = {
        "Native (Your Brand)": NATIVE_PURPLE,
        "Competitor Average": COMP_AVG_SLATE,
    }

    fig = go.Figure()
    for col in value_cols:
        color = color_map.get(col, None)
        if "Rank 1" in col:
            color = "#00695C"
        elif "Rank 2" in col:
            color = "#0097A7"
        elif "Rank 3" in col:
            color = "#B0BEC5"
        fig.add_trace(go.Bar(
            x=df[date_col], y=df[col], name=col, marker_color=color,
            hovertemplate=f"<b>{col}</b><br>%{{x}}<br>%{{y:.1f}}%<extra></extra>",
        ))

    _add_events(fig, date_col, df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=420, barmode="group",
        yaxis=dict(title="Share of Voice (%)", ticksuffix="%"),
    ))
    return fig


def create_amazon_pi_sov_simple_chart(df, title="", subtitle=""):
    """Line chart — only Native vs Competitor Average."""
    if df.empty:
        return None

    date_col = df.columns[0]
    yb_col = [c for c in df.columns if "Your Brand" in c]
    ca_col = [c for c in df.columns if "Competitor Average" in c]
    if not yb_col or not ca_col:
        return None

    fig = go.Figure()
    # Competitor avg first (so fill goes between them)
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[ca_col[0]],
        mode="lines+markers", name="Competitor Average",
        line=dict(color=COMP_AVG_SLATE, width=2.5, shape="spline"),
        marker=dict(size=4),
        hovertemplate="<b>Comp Avg</b><br>%{x}<br>%{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[yb_col[0]],
        mode="lines+markers", name="Native",
        line=dict(color=NATIVE_PURPLE, width=3, shape="spline"),
        marker=dict(size=5), fill="tonexty",
        fillcolor="rgba(110, 66, 229, 0.08)",
        hovertemplate="<b>Native</b><br>%{x}<br>%{y:.1f}%<extra></extra>",
    ))

    _add_events(fig, date_col, df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=400,
        yaxis=dict(title="Share of Voice (%)", ticksuffix="%"),
    ))
    return fig


def create_amazon_pi_sov_vs_rank1_chart(df, title="", subtitle=""):
    """Area chart — Native SoV / Rank 1 SoV * 100."""
    if df.empty:
        return None

    date_col = df.columns[0]
    yb_col = [c for c in df.columns if "Your Brand" in c]
    rank1_col = [c for c in df.columns if "Rank 1" in c]
    if not yb_col or not rank1_col:
        return None

    native_vals = pd.to_numeric(df[yb_col[0]], errors="coerce").fillna(0)
    rank1_vals = pd.to_numeric(df[rank1_col[0]], errors="coerce").fillna(0)
    pct = (native_vals / rank1_vals * 100).where(rank1_vals > 0, 0).round(1)

    rank1_name = rank1_col[0].split("(")[0].strip() if "(" in rank1_col[0] else "Rank 1"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[date_col], y=pct,
        mode="lines+markers",
        name=f"Native as % of {rank1_name}",
        line=dict(color=NATIVE_PURPLE, width=3, shape="spline"),
        marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(110, 66, 229, 0.06)",
        hovertemplate="<b>%{x}</b><br>%{y:.0f}% of " + rank1_name + "<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dot", line_color=UC_GRAY_400, line_width=1.5,
                  annotation_text="Parity", annotation_position="top left",
                  annotation_font=dict(size=11, color=UC_GRAY_500))

    _add_events(fig, date_col, df)

    fig.update_layout(**_base_layout(
        title=dict(text=_title_html(title, subtitle)),
        height=360,
        yaxis=dict(title=f"Native as % of {rank1_name}", ticksuffix="%"),
    ))
    return fig
