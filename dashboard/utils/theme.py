"""
Native by Urban Company — Brand Theme
Design tokens aligned with urbancompany.com/native-ro-water-purifier
"""

# ── UC / Native Brand Colors ──────────────────────────────────────
UC_PURPLE = "#6E42E5"          # UC primary brand purple
UC_PURPLE_LIGHT = "#EDE9FC"
UC_PURPLE_DARK = "#5530B8"
UC_BLACK = "#212121"
UC_WHITE = "#FFFFFF"
UC_BG = "#FAFAFA"
UC_GRAY_50 = "#FAFAFA"
UC_GRAY_100 = "#F5F5F5"
UC_GRAY_200 = "#E8E8E8"
UC_GRAY_400 = "#BBBBBB"
UC_GRAY_500 = "#8C8C8C"
UC_GRAY_700 = "#555555"
UC_GRAY_800 = "#333333"
UC_TEAL = "#009688"            # UC secondary accent
UC_GREEN = "#0F9D58"
UC_GREEN_LIGHT = "#E6F4EA"
UC_RED = "#DD0017"
UC_RED_LIGHT = "#FDE7EA"
UC_AMBER = "#F9A825"
UC_AMBER_LIGHT = "#FFF8E1"

# ── Chart Palette ──────────────────────────────────────────────────
NATIVE_PURPLE = UC_PURPLE       # Native = UC purple (brand color)
AQUA_BLUE = "#1A73E8"
KENT_GREEN = "#0F9D58"
ATOMBERG_TEAL = UC_TEAL
COMP_AVG_SLATE = "#78909C"

# Event annotations — major interventions
EVENTS = [
    {
        "date": "2025-02-22",
        "week": "2025-02-17",
        "month": "2025-02",
        "label": "Dhruv Rathee video",
        "color": "#F9A825",
    },
    {
        "date": "2025-03-01",
        "week": "2025-02-24",
        "month": "2025-03",
        "label": "1st Brand Campaign",
        "color": UC_PURPLE,
    },
    {
        "date": "2025-06-15",
        "week": "2025-06-16",
        "month": "2025-06",
        "label": "Ind-Eng Campaign",
        "color": UC_PURPLE_DARK,
    },
]

BRAND_COLORS = {
    "instahelp": {
        "InstaHelp (Urban Company)": UC_PURPLE,
        "Snabbit": "#DD0017",
        "Pronto": "#F9A825",
        "Category Baseline (Unbranded)": UC_GRAY_500,
        "urban company maid": UC_PURPLE,
        "snabbit": "#DD0017",
        "instamaids": UC_GREEN,
        "pronto maid": "#F9A825",
        "maid service app": UC_TEAL,
        "house maid near me": "#0097A7",
        "domestic help": UC_GRAY_500,
    },
    "native": {
        # Display names
        "Native (Urban Company)": NATIVE_PURPLE,
        "Aquaguard (Eureka Forbes)": AQUA_BLUE,
        "Kent RO Systems": KENT_GREEN,
        "Atomberg Intellon": ATOMBERG_TEAL,
        "Category Baseline (Unbranded)": UC_GRAY_500,
        # Keyword-level
        "native water purifier": NATIVE_PURPLE,
        "aquaguard water purifier": AQUA_BLUE,
        "kent water purifier": KENT_GREEN,
        "atomberg water purifier": ATOMBERG_TEAL,
        "atomberg intellon": "#00796B",
        "uc water purifier": "#AB47BC",
        # Full Market SoS%
        "native water purifier SoS% (Full Market)": NATIVE_PURPLE,
        "aquaguard water purifier SoS% (Full Market)": AQUA_BLUE,
        "kent water purifier SoS% (Full Market)": KENT_GREEN,
        "atomberg water purifier SoS% (Full Market)": ATOMBERG_TEAL,
        # Challenger SoS%
        "native water purifier SoS% (Challenger)": NATIVE_PURPLE,
        "atomberg intellon SoS% (Challenger)": "#00796B",
        "atomberg water purifier SoS% (Challenger)": ATOMBERG_TEAL,
        "uc water purifier SoS% (Challenger)": "#AB47BC",
        # 4-week averages
        "(%)Aqua (4wk avg)": AQUA_BLUE,
        "(%)Atomberg (4wk avg)": ATOMBERG_TEAL,
        "(%)Kent (4wk avg)": KENT_GREEN,
        # Monthly KP totals
        "Native (Urban Company) Total": NATIVE_PURPLE,
        "Aquaguard (Eureka Forbes) Total": AQUA_BLUE,
        "Kent RO Systems Total": KENT_GREEN,
        "Atomberg Intellon Total": ATOMBERG_TEAL,
        "Baseline Total": UC_GRAY_500,
        "Market Total": UC_GRAY_700,
        # Monthly SoS%
        "NATIVE SoS%": NATIVE_PURPLE,
        "AQUAGUARD SoS%": AQUA_BLUE,
        "KENT SoS%": KENT_GREEN,
        "(%)Aqua (Monthly)": AQUA_BLUE,
        "(%)Kent (Monthly)": KENT_GREEN,
    },
}


# ── Plotly layout defaults ─────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(
        family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
        size=13, color=UC_GRAY_700,
    ),
    title_font=dict(size=15, color=UC_BLACK),
    legend=dict(
        orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5,
        font=dict(size=11), bgcolor="rgba(0,0,0,0)",
    ),
    margin=dict(l=48, r=24, t=56, b=48),
    plot_bgcolor=UC_WHITE,
    paper_bgcolor=UC_WHITE,
    xaxis=dict(
        gridcolor=UC_GRAY_200, showline=True, linecolor=UC_GRAY_200,
        tickfont=dict(size=11),
    ),
    yaxis=dict(
        gridcolor=UC_GRAY_100, showline=False,
        tickfont=dict(size=11),
    ),
    hoverlabel=dict(
        bgcolor=UC_WHITE, font_size=12,
        font_family="-apple-system, BlinkMacSystemFont, sans-serif",
        bordercolor=UC_GRAY_200,
    ),
)


def get_brand_color(category_id, brand_name):
    colors = BRAND_COLORS.get(category_id, {})
    return colors.get(brand_name, UC_GRAY_500)


def get_category_palette(category_id):
    return BRAND_COLORS.get(category_id, {})
