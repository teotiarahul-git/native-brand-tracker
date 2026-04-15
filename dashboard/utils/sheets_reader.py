"""
Google Sheets data reader for the Streamlit dashboard.
Reads from any category's Google Sheet and caches results.

Supports two auth modes:
  1. Local: reads .config/token.json (development)
  2. Cloud: reads st.secrets["gcp_service_account"] (Streamlit Community Cloud)
"""

import json
import os
import streamlit as st
import gspread
import pandas as pd
from google.oauth2.credentials import Credentials

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CONFIG_DIR = os.path.join(PROJECT_ROOT, ".config")
CATEGORIES_DIR = os.path.join(PROJECT_ROOT, "categories")


def get_sheets_client():
    """Get authenticated gspread client.

    Tries Streamlit secrets first (cloud deploy), then falls back to
    local token.json file (local development).
    """
    # Debug: show what secrets are available (keys only, no values)
    try:
        available_keys = list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else []
        if available_keys:
            st.sidebar.info(f"Secrets detected: {available_keys}")
        else:
            st.sidebar.warning("No secrets found. Add credentials in Settings → Secrets.")
    except Exception:
        st.sidebar.warning("Could not read secrets.")

    # Cloud: service account credentials in st.secrets
    try:
        if "gcp_service_account" in st.secrets:
            from google.oauth2.service_account import Credentials as SACredentials
            sa_info = dict(st.secrets["gcp_service_account"])
            creds = SACredentials.from_service_account_info(
                sa_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive.readonly",
                ],
            )
            return gspread.authorize(creds)
    except Exception as e:
        st.sidebar.warning(f"Service account auth failed: {e}")

    # Cloud fallback: OAuth token in st.secrets
    try:
        if "gcp_oauth_token" in st.secrets:
            token_data = dict(st.secrets["gcp_oauth_token"])
            # Ensure scopes is a proper list (TOML may parse it differently)
            if "scopes" in token_data and isinstance(token_data["scopes"], str):
                token_data["scopes"] = [token_data["scopes"]]
            elif "scopes" not in token_data:
                token_data["scopes"] = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive.readonly",
                ]
            creds = Credentials.from_authorized_user_info(token_data)
            # Force token refresh if expired
            if creds.expired and creds.refresh_token:
                import google.auth.transport.requests
                creds.refresh(google.auth.transport.requests.Request())
            return gspread.authorize(creds)
    except Exception as e:
        st.sidebar.warning(f"OAuth token auth failed: {e}")

    # Local: file-based token
    try:
        token_file = os.path.join(CONFIG_DIR, "token.json")
        creds = Credentials.from_authorized_user_file(token_file)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(
            "**Could not connect to Google Sheets.**\n\n"
            "If running on Streamlit Cloud, add your credentials in "
            "Settings → Secrets. See `.streamlit/secrets.toml.example` for the format.\n\n"
            f"Error: `{e}`"
        )
        st.stop()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_category_config(category_id):
    """Load category configuration."""
    config_path = os.path.join(CATEGORIES_DIR, f"{category_id}.json")
    with open(config_path) as f:
        return json.load(f)


def list_categories():
    """List all available categories."""
    categories = []
    if os.path.exists(CATEGORIES_DIR):
        for f in sorted(os.listdir(CATEGORIES_DIR)):
            if f.endswith(".json"):
                cat_id = f.replace(".json", "")
                config = load_category_config(cat_id)
                categories.append({
                    "id": cat_id,
                    "display_name": config.get("display_name", cat_id),
                    "description": config.get("description", ""),
                    "sheet_url": config.get("google_sheet_url", ""),
                })
    return categories


@st.cache_data(ttl=300)
def load_dashboard_data(category_id):
    """Load normalized Dashboard Data tab as a DataFrame."""
    config = load_category_config(category_id)
    sheet_id = config.get("google_sheet_id", "")
    if not sheet_id:
        return pd.DataFrame()

    gc = get_sheets_client()
    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet("Dashboard Data")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_trends_data(category_id):
    """Load Google Trends data from the sheet.

    Supports two tab formats:
      1. "Trends Indexed Searches" — section-separated with === markers
      2. "Raw_Weekly_Trends" — flat table with Week column (actual format)

    Returns dict of {section_name: {"headers": [...], "rows": [...]}}
    """
    config = load_category_config(category_id)
    sheet_id = config.get("google_sheet_id", "")
    if not sheet_id:
        return {}

    gc = get_sheets_client()
    sh = gc.open_by_key(sheet_id)

    # Try the section-separated format first
    try:
        ws = sh.worksheet("Trends Indexed Searches")
        all_data = ws.get_all_values()

        sections = {}
        current_section = None
        headers = []

        for row in all_data:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()

            if cell.startswith("==="):
                current_section = cell.replace("===", "").strip()
                headers = []
                continue

            if cell == "Week_Start":
                headers = [h for h in row if h]
                continue

            if headers and cell and cell[0].isdigit() and "-" in cell:
                if current_section not in sections:
                    sections[current_section] = {"headers": headers, "rows": []}
                entry = {"Week_Start": cell}
                for i, h in enumerate(headers[1:], 1):
                    if i < len(row) and h and h != "Notes":
                        try:
                            entry[h] = int(row[i]) if row[i] else 0
                        except (ValueError, TypeError):
                            entry[h] = 0
                sections[current_section]["rows"].append(entry)

        if sections:
            return sections
    except Exception:
        pass

    # Fall back to Raw_Weekly_Trends flat format
    try:
        ws = sh.worksheet("Raw_Weekly_Trends")
        all_data = ws.get_all_values()
    except Exception:
        return {}

    if len(all_data) < 2:
        return {}

    headers = all_data[0]

    # Build column groups for sections
    full_market_cols = [h for h in headers if "Full Market" in h]
    challenger_cols = [h for h in headers if "Challenger" in h]
    avg_cols = [h for h in headers if "4wk avg" in h]

    # Branded keyword columns (raw indexed searches)
    native_keywords = [h for h in headers if h.startswith("native ") or h.startswith("uc ") or h.startswith("urban company ")]
    aquaguard_keywords = [h for h in headers if h.startswith("aquaguard ") or h.startswith("eureka forbes")]
    kent_keywords = [h for h in headers if h.startswith("kent ")]
    atomberg_keywords = [h for h in headers if h.startswith("atomberg ")]

    def _build_section(col_list, section_name):
        """Build a section dict from a list of column names."""
        if not col_list:
            return None
        sec_headers = ["Week_Start"] + col_list
        rows = []
        for row in all_data[1:]:
            if not row or not row[0]:
                continue
            entry = {"Week_Start": row[0]}
            for col_name in col_list:
                idx = headers.index(col_name)
                try:
                    entry[col_name] = float(row[idx]) if idx < len(row) and row[idx] else 0
                except (ValueError, TypeError):
                    entry[col_name] = 0
            rows.append(entry)
        return {"headers": sec_headers, "rows": rows}

    sections = {}

    if full_market_cols:
        sec = _build_section(full_market_cols, "Share of Search — Full Market")
        if sec:
            sections["Share of Search — Full Market"] = sec

    if challenger_cols:
        sec = _build_section(challenger_cols, "Share of Search — Challenger")
        if sec:
            sections["Share of Search — Challenger"] = sec

    if avg_cols:
        sec = _build_section(avg_cols, "Competitor Share of Search (4-Week Average)")
        if sec:
            sections["Competitor Share of Search (4-Week Average)"] = sec

    # Build a combined brand view with representative keywords
    brand_cols = []
    for name in ["native water purifier", "aquaguard water purifier",
                  "kent water purifier", "atomberg water purifier"]:
        if name in headers:
            brand_cols.append(name)
    if brand_cols:
        sec = _build_section(brand_cols, "Brand Keyword Indexed Searches")
        if sec:
            sections["Brand Keyword Indexed Searches"] = sec

    return sections


@st.cache_data(ttl=300)
def load_volume_data(category_id):
    """Load Monthly Search Volume data from the sheet.

    Supports two tab formats:
      1. "Monthly Search Volume" — section-separated with === markers
      2. "Raw_Monthly_KP" — flat table with Month column (actual format)

    Returns dict of {section_name: {"headers": [...], "rows": [...]}}
    """
    config = load_category_config(category_id)
    sheet_id = config.get("google_sheet_id", "")
    if not sheet_id:
        return {}

    gc = get_sheets_client()
    sh = gc.open_by_key(sheet_id)

    # Try section-separated format first
    try:
        ws = sh.worksheet("Monthly Search Volume")
        all_data = ws.get_all_values()

        sections = {}
        current_section = None
        headers = []

        for row in all_data:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()

            if cell.startswith("==="):
                current_section = cell.replace("===", "").strip()
                headers = []
                continue

            if cell == "Month":
                headers = [h for h in row if h]
                continue

            if headers and cell and "-" in cell and len(cell) == 7:
                if current_section not in sections:
                    sections[current_section] = {"headers": headers, "rows": []}
                entry = {"Month": cell}
                for i, h in enumerate(headers[1:], 1):
                    if i < len(row) and h and h not in ("Notes",):
                        try:
                            entry[h] = int(str(row[i]).replace(",", "")) if row[i] else 0
                        except (ValueError, TypeError):
                            entry[h] = 0
                sections[current_section]["rows"].append(entry)

        if sections:
            return sections
    except Exception:
        pass

    # Fall back to Raw_Monthly_KP flat format
    try:
        ws = sh.worksheet("Raw_Monthly_KP")
        all_data = ws.get_all_values()
    except Exception:
        return {}

    if len(all_data) < 2:
        return {}

    headers = all_data[0]

    # Identify brand total and SoS% columns
    total_cols = [h for h in headers if h.endswith(" Total")]
    sos_cols = [h for h in headers if h.endswith(" SoS%")]

    def _build_section(col_list, section_name):
        if not col_list:
            return None
        sec_headers = ["Month"] + [f"{c} Volume" if not c.endswith("Volume") else c for c in col_list]
        rows = []
        for row in all_data[1:]:
            if not row or not row[0] or "-" not in row[0] or len(row[0]) != 7:
                continue
            entry = {"Month": row[0]}
            for col_name in col_list:
                idx = headers.index(col_name)
                h_name = f"{col_name} Volume" if not col_name.endswith("Volume") else col_name
                try:
                    entry[h_name] = int(str(row[idx]).replace(",", "")) if idx < len(row) and row[idx] else 0
                except (ValueError, TypeError):
                    entry[h_name] = 0
            rows.append(entry)
        return {"headers": sec_headers, "rows": rows}

    def _build_section_raw(col_list, section_name):
        """Build section without adding ' Volume' suffix."""
        if not col_list:
            return None
        sec_headers = ["Month"] + col_list
        rows = []
        for row in all_data[1:]:
            if not row or not row[0] or "-" not in row[0] or len(row[0]) != 7:
                continue
            entry = {"Month": row[0]}
            for col_name in col_list:
                idx = headers.index(col_name)
                try:
                    val = row[idx] if idx < len(row) else ""
                    entry[col_name] = float(val) if val else 0
                except (ValueError, TypeError):
                    entry[col_name] = 0
            rows.append(entry)
        return {"headers": sec_headers, "rows": rows}

    sections = {}

    if total_cols:
        sec = _build_section(total_cols, "Brand Total Volume")
        if sec:
            sections["Brand Total Volume"] = sec

    if sos_cols:
        sec = _build_section_raw(sos_cols, "Share of Search (%)")
        if sec:
            sections["Share of Search (%)"] = sec

    # Native as % of individual competitors (monthly)
    pct_monthly_cols = [h for h in headers if h.startswith("(%)") and "Monthly" in h]
    if pct_monthly_cols:
        sec = _build_section_raw(pct_monthly_cols, "Native as % of Competitors (Monthly)")
        if sec:
            sections["Native as % of Competitors (Monthly)"] = sec

    return sections


@st.cache_data(ttl=300)
def load_amazon_pi_data(category_id):
    """Load Amazon Pi Brand Recall and Ad SoV data as DataFrames.
    Returns dict: {
        'brand_recall_monthly': DataFrame,
        'brand_recall_weekly': DataFrame,
        'ad_sov_monthly': DataFrame,
        'ad_sov_weekly': DataFrame,
    }
    """
    config = load_category_config(category_id)
    sheet_id = config.get("google_sheet_id", "")
    if not sheet_id:
        return {}

    gc = get_sheets_client()
    sh = gc.open_by_key(sheet_id)

    result = {}
    tab_map = {
        "brand_recall_monthly": "Amazon Pi - Brand Recall (Monthly)",
        "brand_recall_weekly": "Amazon Pi - Brand Recall (Weekly)",
        "ad_sov_monthly": "Amazon Pi - Ad Share of Voice (Monthly)",
        "ad_sov_weekly": "Amazon Pi - Ad Share of Voice (Weekly)",
    }

    for key, tab_name in tab_map.items():
        try:
            ws = sh.worksheet(tab_name)
            all_data = ws.get_all_values()
            if len(all_data) > 4:
                headers = all_data[3]  # Row 4 is header
                rows = all_data[4:]   # Row 5+ is data
                df = pd.DataFrame(rows, columns=headers)
                # Convert numeric columns
                for col in df.columns:
                    if col not in ("Month", "Week_Start", "Notes"):
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                result[key] = df
            else:
                result[key] = pd.DataFrame()
        except Exception:
            result[key] = pd.DataFrame()

    return result


@st.cache_data(ttl=300)
def load_gsc_data(category_id):
    """Load Google Search Console tab as a DataFrame."""
    config = load_category_config(category_id)
    sheet_id = config.get("google_sheet_id", "")
    if not sheet_id:
        return pd.DataFrame()

    gc = get_sheets_client()
    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet("Google Search Console")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()
