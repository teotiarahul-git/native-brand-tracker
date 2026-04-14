"""
Urban Company Brand Awareness Tracker — Main Dashboard
Clean, professional UC-branded landing page with category navigation.
"""

import streamlit as st
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PROJECT_ROOT)

from dashboard.utils.sheets_reader import list_categories

st.set_page_config(
    page_title="Urban Company — Brand Awareness Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for UC branding
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #000000;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #8C8C8C;
        margin-bottom: 2rem;
    }
    .category-card {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        transition: border-color 0.2s;
    }
    .category-card:hover {
        border-color: #4A90D9;
    }
    .category-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #000000;
        margin-bottom: 0.5rem;
    }
    .category-desc {
        font-size: 0.9rem;
        color: #8C8C8C;
    }
    .stApp {
        background-color: #F7F7F7;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">Urban Company</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Brand Awareness Tracker — Marketing Intelligence Platform</p>', unsafe_allow_html=True)

# Load categories
categories = list_categories()

if not categories:
    st.warning("No categories configured. Create a category config in the `categories/` directory.")
    st.stop()

st.markdown("### Categories")
st.markdown("Select a category to view its brand awareness dashboard.")

# Category cards
cols = st.columns(min(len(categories), 3))
for i, cat in enumerate(categories):
    with cols[i % 3]:
        with st.container():
            st.markdown(f"""
            <div class="category-card">
                <div class="category-title">{cat['display_name']}</div>
                <div class="category-desc">{cat['description']}</div>
            </div>
            """, unsafe_allow_html=True)

            if cat.get("sheet_url"):
                col1, col2 = st.columns(2)
                with col1:
                    st.page_link(f"pages/{cat['id']}.py", label=f"Open Dashboard", icon="📊")
                with col2:
                    st.link_button("Google Sheet", cat["sheet_url"], use_container_width=True)
            else:
                st.page_link(f"pages/{cat['id']}.py", label=f"Open Dashboard", icon="📊")

# Footer
st.markdown("---")
st.caption("Data sources: Google Trends (weekly indexed searches) · Google Ads Keyword Planner (monthly volumes) · Google Search Console (weekly branded performance)")
