#!/usr/bin/env python3
"""
Update Dashboard, City Summary, and Dashboard Data tabs from collected data.

Usage: python3 dashboard_updater.py --category instahelp
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import (
    load_category_config, load_keywords, load_geo_codes,
    open_category_sheet, get_or_create_worksheet
)


def read_latest_trends(sh):
    """Read latest indexed search data from Trends tab.
    Returns dict keyed by section header (e.g. 'All India — Direct Competition ...').
    Each value is a list of weekly entries with {week_start, term1: idx, term2: idx, ...}.
    """
    try:
        ws = sh.worksheet("Trends Indexed Searches")
        all_data = ws.get_all_values()
    except Exception:
        return {}

    geo_data = {}
    current_geo = None
    headers = []

    for row in all_data:
        if not row or not row[0]:
            continue
        cell = str(row[0]).strip()

        if cell.startswith("==="):
            current_geo = cell.replace("===", "").strip()
            headers = []
            continue

        if cell == "Week_Start":
            headers = row
            continue

        if headers and cell and cell[0].isdigit() and "-" in cell:
            if current_geo:
                if current_geo not in geo_data:
                    geo_data[current_geo] = []
                entry = {"week_start": cell}
                for i, h in enumerate(headers[1:], 1):
                    if i < len(row) and h and h != "Notes":
                        try:
                            entry[h] = int(row[i]) if row[i] else 0
                        except (ValueError, TypeError):
                            entry[h] = 0
                geo_data[current_geo].append(entry)

    return geo_data


def read_latest_volumes(sh):
    """Read latest monthly volume data.
    Returns dict keyed by geo label (e.g. 'All India', 'Delhi').
    Each value is a list of monthly entries.
    """
    try:
        ws = sh.worksheet("Monthly Search Volume")
        all_data = ws.get_all_values()
    except Exception:
        return {}

    geo_data = {}
    current_geo = None
    headers = []

    for row in all_data:
        if not row or not row[0]:
            continue
        cell = str(row[0]).strip()

        if cell.startswith("==="):
            current_geo = cell.replace("===", "").strip()
            headers = []
            continue

        if cell == "Month":
            headers = row
            continue

        if headers and cell and "-" in cell and len(cell) == 7:
            if current_geo:
                if current_geo not in geo_data:
                    geo_data[current_geo] = []
                entry = {"month": cell}
                for i, h in enumerate(headers[1:], 1):
                    if i < len(row) and h and h != "Notes":
                        try:
                            entry[h] = int(row[i].replace(",", "")) if row[i] else 0
                        except (ValueError, TypeError):
                            entry[h] = 0
                geo_data[current_geo].append(entry)

    return geo_data


def read_latest_gsc(sh):
    """Read latest GSC data."""
    try:
        ws = sh.worksheet("Google Search Console")
        all_data = ws.get_all_values()
    except Exception:
        return []

    if len(all_data) < 2:
        return []

    headers = all_data[0]
    rows = []
    for row in all_data[1:]:
        if row and row[0]:
            entry = {}
            for i, h in enumerate(headers):
                if i < len(row):
                    entry[h] = row[i]
            rows.append(entry)
    return rows


def read_latest_amazon_pi(sh):
    """Read latest Amazon Pi Brand Recall and Ad SoV data.
    Returns dict with 'brand_recall_monthly', 'brand_recall_weekly',
    'ad_sov_monthly', 'ad_sov_weekly' keys, each a list of row dicts.
    """
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
                headers = all_data[3]  # Row 4 = header row
                entries = []
                for row in all_data[4:]:  # Row 5+ = data
                    if row and row[0]:
                        entry = {}
                        for i, h in enumerate(headers):
                            if i < len(row) and h:
                                try:
                                    entry[h] = float(row[i]) if row[i] and row[i].replace('.', '', 1).replace('-', '', 1).isdigit() else row[i]
                                except (ValueError, TypeError):
                                    entry[h] = row[i]
                        entries.append(entry)
                result[key] = entries
        except Exception:
            result[key] = []
    return result


def write_dashboard_kpis(sh, trends_data, volume_data, gsc_data, keywords_data, geo_codes, category_config):
    """Write computed KPIs to the Dashboard tab."""
    ws = get_or_create_worksheet(sh, "Dashboard", rows=100, cols=6)

    brand_keys = list(keywords_data["brands"].keys())
    brand_names = [keywords_data["brands"][k]["display_name"] for k in brand_keys]
    configured_geos = category_config.get("geos", ["india"])
    geo_labels = [geo_codes.get(g, {}).get("label", g) for g in configured_geos]

    # Build the complete Dashboard content
    rows = [
        [f"{category_config['display_name']} — Brand Awareness Tracker", "", "", "", ""],
        [f"Coverage: {', '.join(geo_labels)}", "", "", "", ""],
        ["Sources: Google Trends (weekly) · Google Ads Keyword Planner (monthly) · Google Search Console", "", "", "", ""],
        ["", "", "", "", ""],
    ]

    # --- All India Summary: Trends ---
    rows.append(["--- Google Trends: Latest Indexed Searches (All India) ---", "", "", "", ""])
    rows.append(["Brand", "Latest Index", "Week", "Previous Week Index", "Change"])

    # Find the All India direct competition section
    india_direct_key = None
    for k in trends_data:
        if "All India" in k and "Direct" in k:
            india_direct_key = k
            break

    if india_direct_key and trends_data[india_direct_key]:
        weeks = trends_data[india_direct_key]
        latest = weeks[-1] if weeks else {}
        prev = weeks[-2] if len(weeks) >= 2 else {}
        week_str = latest.get("week_start", "")
        prev_week_str = prev.get("week_start", "")
        for term in latest:
            if term != "week_start":
                curr_val = latest.get(term, 0)
                prev_val = prev.get(term, 0)
                change = curr_val - prev_val if prev_val else ""
                rows.append([term, curr_val, week_str, prev_val if prev_val else "", change])
    else:
        rows.append(["No trends data collected yet", "", "", "", ""])

    rows.append(["", "", "", "", ""])

    # Category view
    india_cat_key = None
    for k in trends_data:
        if "All India" in k and "Category" in k:
            india_cat_key = k
            break

    if india_cat_key and trends_data[india_cat_key]:
        rows.append(["--- Google Trends: Category View (All India) ---", "", "", "", ""])
        rows.append(["Term", "Latest Index", "Week", "Previous Week Index", "Change"])
        weeks = trends_data[india_cat_key]
        latest = weeks[-1] if weeks else {}
        prev = weeks[-2] if len(weeks) >= 2 else {}
        week_str = latest.get("week_start", "")
        for term in latest:
            if term != "week_start":
                curr_val = latest.get(term, 0)
                prev_val = prev.get(term, 0)
                change = curr_val - prev_val if prev_val else ""
                rows.append([term, curr_val, week_str, prev_val if prev_val else "", change])
        rows.append(["", "", "", "", ""])

    # --- All India Summary: Volumes ---
    rows.append(["--- Monthly Search Volume: All India (Google Ads Keyword Planner) ---", "", "", "", ""])
    rows.append(["Brand", "Monthly Volume", "Month", "", ""])

    india_vol = volume_data.get("All India", [])
    if india_vol:
        latest_vol = india_vol[-1]
        month_str = latest_vol.get("month", "")
        for key, val in latest_vol.items():
            if key not in ("month", "Total Market", "Notes") and val:
                rows.append([key.replace(" Volume", ""), f"{val:,}" if isinstance(val, int) else val, month_str, "", ""])
        total_mkt = latest_vol.get("Total Market", 0)
        if total_mkt:
            rows.append(["Total Market", f"{total_mkt:,}" if isinstance(total_mkt, int) else total_mkt, month_str, "", ""])
    else:
        rows.append(["No volume data collected yet", "", "", "", ""])

    rows.append(["", "", "", "", ""])

    # --- GSC Summary ---
    rows.append(["--- Google Search Console: Branded Performance (All India) ---", "", "", "", ""])
    if gsc_data:
        latest_gsc = gsc_data[-1]
        rows.append(["Metric", "Value", "Week", "", ""])
        for key, val in latest_gsc.items():
            if key != "Notes" and val:
                rows.append([key, val, latest_gsc.get("Week_Start", ""), "", ""])
    else:
        rows.append(["No Google Search Console data yet (check access permissions)", "", "", "", ""])

    rows.append(["", "", "", "", ""])

    # --- Amazon Pi Summary ---
    pi_config = category_config.get("amazon_pi", {})
    if pi_config.get("enabled"):
        rows.append(["--- Amazon Pi: Brand Intelligence ---", "", "", "", ""])
        amazon_pi_data = read_latest_amazon_pi(sh)

        recall_monthly = amazon_pi_data.get("brand_recall_monthly", [])
        if recall_monthly:
            latest = recall_monthly[-1]
            date_col = list(latest.keys())[0]
            yb_col = [k for k in latest if "Rebased Index" in str(k) or "Your Brand" in str(k)]
            ca_col = [k for k in latest if "Competitor" in str(k)]
            pct_col = [k for k in latest if "%" in str(k) or "vs" in str(k).lower()]
            rows.append(["Metric", "Value", "Period", "", ""])
            yb_val = latest.get(yb_col[0], 0) if yb_col else 0
            ca_val = latest.get(ca_col[0], 0) if ca_col else 0
            pct_val = latest.get(pct_col[0], 0) if pct_col else 0
            rows.append(["Brand Recall (Monthly)", f"Native search {pct_val}% vs Competitor average, Native Index: {yb_val}, Competitor Index: {ca_val}", latest.get(date_col, ""), "", ""])

        sov_monthly = amazon_pi_data.get("ad_sov_monthly", [])
        if sov_monthly:
            latest = sov_monthly[-1]
            date_col = list(latest.keys())[0]
            yb_col = [k for k in latest if "Your Brand" in str(k)]
            ca_col = [k for k in latest if "Competitor" in str(k)]
            yb_val = latest.get(yb_col[0], 0) if yb_col else 0
            ca_val = latest.get(ca_col[0], 0) if ca_col else 0
            rows.append(["Ad Share of Voice (Monthly)", f"Native: {yb_val}%, Competitor Avg: {ca_val}%", latest.get(date_col, ""), "", ""])

        if not recall_monthly and not sov_monthly:
            rows.append(["No Amazon Pi data available yet", "", "", "", ""])

    rows.append(["", "", "", "", ""])

    # --- City Spotlight ---
    rows.append(["--- City Spotlight: Latest Indexed Searches ---", "", "", "", ""])
    # Collect all direct competition sections by city
    city_trends = {}
    for section_key, section_weeks in trends_data.items():
        if "Direct" in section_key and section_weeks:
            city_name = section_key.split(" — ")[0]
            latest = section_weeks[-1]
            city_trends[city_name] = latest

    if city_trends:
        # Build header from first city's terms
        first_city = list(city_trends.values())[0]
        term_names = [k for k in first_city if k != "week_start"]
        rows.append(["City"] + term_names)

        for city_name, latest in city_trends.items():
            row = [city_name]
            for term in term_names:
                row.append(latest.get(term, 0))
            rows.append(row)
    else:
        rows.append(["No city-level trends data available", "", "", "", ""])

    rows.append(["", "", "", "", ""])

    # --- City Spotlight: Volumes ---
    rows.append(["--- City Spotlight: Monthly Search Volumes ---", "", "", "", ""])
    if volume_data:
        # Get headers from first geo
        first_geo_vols = list(volume_data.values())[0]
        if first_geo_vols:
            vol_keys = [k for k in first_geo_vols[-1] if k not in ("month", "Total Market", "Notes")]
            rows.append(["City"] + [k.replace(" Volume", "") for k in vol_keys])

            for geo_label, months in volume_data.items():
                if months:
                    latest = months[-1]
                    row = [geo_label]
                    for k in vol_keys:
                        val = latest.get(k, 0)
                        row.append(f"{val:,}" if isinstance(val, int) else val)
                    rows.append(row)

    rows.append(["", "", "", "", ""])

    # --- Watch-For Signals ---
    rows.append(["--- Active Signals ---", "", "", "", ""])
    rows.append(["Signal", "What It Means", "Recommended Action", "", ""])

    signals = detect_signals(trends_data, volume_data, gsc_data)
    if signals:
        for sig in signals:
            rows.append([sig["title"], sig["description"], sig.get("action", ""), "", ""])
    else:
        rows.append(["No active signals detected this week", "", "", "", ""])

    # Pad and write
    max_cols = max(len(r) for r in rows)
    rows = [r + [""] * (max_cols - len(r)) for r in rows]

    # Sanitize
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                rows[i][j] = 0

    end_col = chr(64 + min(max_cols, 26))
    ws.update(range_name=f"A1:{end_col}{len(rows)}", values=rows)
    print(f"  Dashboard tab updated ({len(rows)} rows with KPIs, city spotlights, signals).")


def write_city_summary(sh, trends_data, volume_data, keywords_data, geo_codes, category_config):
    """Write computed city-level data to City Summary tab."""
    ws = get_or_create_worksheet(sh, "City Summary", rows=20, cols=15)

    brand_keys = list(keywords_data["brands"].keys())
    brand_names = [keywords_data["brands"][k]["display_name"] for k in brand_keys]
    configured_geos = category_config.get("geos", ["india"])

    # Headers
    header = ["City"]
    for bn in brand_names:
        header.append(f"{bn} Index (Trends)")
    for bn in brand_names:
        header.append(f"{bn} Volume (Monthly)")
    header.append("Category Baseline Volume")

    all_rows = [header]

    for geo_name in configured_geos:
        geo_info = geo_codes.get(geo_name, {})
        geo_label = geo_info.get("label", geo_name)

        row = [geo_label]

        # Find latest trends index for this city (direct competition set)
        city_indices = {}
        for section_key, section_weeks in trends_data.items():
            if geo_label in section_key and "Direct" in section_key and section_weeks:
                latest = section_weeks[-1]
                for k, v in latest.items():
                    if k != "week_start":
                        city_indices[k] = v
                break

        # Map trends terms to brand names (best effort)
        trends_terms = category_config.get("trends_sets", {}).get("direct_competition", {}).get("terms", [])
        for bn in brand_names:
            # Find the matching trends term for this brand
            matched = False
            for term in trends_terms:
                if term in city_indices:
                    row.append(city_indices[term])
                    trends_terms = [t for t in trends_terms if t != term]  # Don't reuse
                    matched = True
                    break
            if not matched:
                row.append(0)

        # Find latest volume for this city
        vol_entry = volume_data.get(geo_label, [])
        if vol_entry:
            latest_vol = vol_entry[-1]
            for bn in brand_names:
                # Try to match volume column header
                vol_key = f"{bn} Volume"
                row.append(latest_vol.get(vol_key, 0))
            row.append(latest_vol.get("Category Baseline", 0))
        else:
            for bn in brand_names:
                row.append(0)
            row.append(0)

        all_rows.append(row)

    # Pad and write
    max_cols = max(len(r) for r in all_rows)
    all_rows = [r + [""] * (max_cols - len(r)) for r in all_rows]

    end_col = chr(64 + min(max_cols, 26))
    ws.update(range_name=f"A1:{end_col}{len(all_rows)}", values=all_rows)
    print(f"  City Summary tab updated ({len(all_rows) - 1} cities).")


def detect_signals(trends_data, volume_data, gsc_data):
    """Detect watch-for signals from the data."""
    signals = []

    # Check Snabbit dominance
    for section_key, weeks in trends_data.items():
        if "All India" in section_key and "Direct" in section_key and weeks:
            latest = weeks[-1]
            snabbit_idx = latest.get("snabbit", 0)
            uc_maid_idx = latest.get("urban company maid", 0)
            instamaids_idx = latest.get("instamaids", 0)
            uc_total = uc_maid_idx + instamaids_idx

            if snabbit_idx > 0 and uc_total == 0:
                signals.append({
                    "title": "Snabbit has search presence, InstaHelp has near-zero",
                    "description": f"Snabbit index: {snabbit_idx}, UC maid + instamaids: {uc_total}",
                    "action": "Invest in brand awareness campaigns to build search presence",
                    "severity": "warning",
                })

            # Check week-over-week changes
            if len(weeks) >= 2:
                prev = weeks[-2]
                snabbit_prev = prev.get("snabbit", 0)
                if snabbit_idx > snabbit_prev and snabbit_prev > 0:
                    pct_change = round((snabbit_idx - snabbit_prev) / snabbit_prev * 100)
                    if pct_change > 20:
                        signals.append({
                            "title": f"Snabbit indexed searches rising (+{pct_change}% week-over-week)",
                            "description": f"Was {snabbit_prev}, now {snabbit_idx}",
                            "action": "Monitor Snabbit campaigns; consider competitive response",
                            "severity": "warning",
                        })

    # Check volume data
    india_vol = volume_data.get("All India", [])
    if india_vol:
        latest = india_vol[-1]
        baseline = 0
        total_branded = 0
        for k, v in latest.items():
            if "Category Baseline" in k:
                baseline = v
            elif "Volume" in k and isinstance(v, int):
                total_branded += v

        if baseline > total_branded:
            signals.append({
                "title": "Category baseline searches exceed all branded searches combined",
                "description": f"Unbranded demand ({baseline:,}) > all brands ({total_branded:,})",
                "action": "Large unbranded market — opportunity to capture with brand campaigns",
                "severity": "info",
            })

    # Check city divergences in volumes
    for geo_label, months in volume_data.items():
        if geo_label != "All India" and months:
            latest = months[-1]
            for k, v in latest.items():
                if "InstaHelp" in k and isinstance(v, int) and v == 0:
                    signals.append({
                        "title": f"InstaHelp has zero search volume in {geo_label}",
                        "description": f"No branded searches detected for InstaHelp in {geo_label}",
                        "action": f"Consider targeted awareness campaigns in {geo_label}",
                        "severity": "warning",
                    })
                    break  # One signal per city

    return signals


def write_dashboard_data(sh, trends_data, volume_data, gsc_data):
    """Write normalized long-format data for Streamlit dashboard."""
    ws = get_or_create_worksheet(sh, "Dashboard Data", rows=5000, cols=6)

    rows = [["Date", "Geo", "Source", "Brand", "Metric", "Value"]]

    for geo_label, weeks in trends_data.items():
        for week in weeks:
            week_start = week.get("week_start", "")
            for key, val in week.items():
                if key != "week_start":
                    rows.append([week_start, geo_label, "Google Trends", key, "indexed_searches", val])

    for geo_label, months in volume_data.items():
        for month_entry in months:
            month = month_entry.get("month", "")
            for key, val in month_entry.items():
                if key not in ("month", "Total Market", "Notes"):
                    rows.append([month, geo_label, "Google Ads Keyword Planner", key, "monthly_volume", val])

    for entry in gsc_data:
        week = entry.get("Week_Start", "")
        if week:
            rows.append([week, "All India", "Google Search Console", "Brand", "impressions", entry.get("Total Branded Impressions", 0)])
            rows.append([week, "All India", "Google Search Console", "Brand", "clicks", entry.get("Total Branded Clicks", 0)])
            rows.append([week, "All India", "Google Search Console", "Brand", "click_through_rate", entry.get("Click-Through Rate %", 0)])
            rows.append([week, "All India", "Google Search Console", "Brand", "avg_position", entry.get("Avg Position", 0)])

    # Amazon Pi data
    amazon_pi_data = read_latest_amazon_pi(sh)
    for key_prefix, entries in [("brand_recall_monthly", amazon_pi_data.get("brand_recall_monthly", [])),
                                 ("brand_recall_weekly", amazon_pi_data.get("brand_recall_weekly", []))]:
        metric = "brand_recall_index"
        for entry in entries:
            date_col = list(entry.keys())[0]
            date_val = entry.get(date_col, "")
            yb_col = [k for k in entry if "Your Brand" in str(k)]
            ca_col = [k for k in entry if "Competitor" in str(k)]
            if yb_col:
                rows.append([date_val, "Amazon", "Amazon Pi", "Native", metric, entry.get(yb_col[0], 0)])
            if ca_col:
                rows.append([date_val, "Amazon", "Amazon Pi", "Competitor Average", metric, entry.get(ca_col[0], 0)])

    for key_prefix, entries in [("ad_sov_monthly", amazon_pi_data.get("ad_sov_monthly", [])),
                                 ("ad_sov_weekly", amazon_pi_data.get("ad_sov_weekly", []))]:
        metric = "ad_sov_pct"
        for entry in entries:
            date_col = list(entry.keys())[0]
            date_val = entry.get(date_col, "")
            for col_key, brand_label in [("Your Brand", "Native"), ("Competitor", "Competitor Average")]:
                matched = [k for k in entry if col_key in str(k)]
                if matched:
                    rows.append([date_val, "Amazon", "Amazon Pi", brand_label, metric, entry.get(matched[0], 0)])
            # Also add Rank 1/2 if present
            for col_key in entry:
                if "Rank 1" in str(col_key) or "Rank 2" in str(col_key):
                    brand_label = str(col_key).split("(")[0].strip() if "(" in str(col_key) else str(col_key)
                    rows.append([date_val, "Amazon", "Amazon Pi", brand_label, metric, entry.get(col_key, 0)])

    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                rows[i][j] = 0

    ws.update(range_name=f"A1:F{len(rows)}", values=rows)
    print(f"  Dashboard Data tab updated ({len(rows)} rows).")


def main():
    parser = argparse.ArgumentParser(description="Update dashboard tabs")
    parser.add_argument("--category", required=True, help="Category ID")
    args = parser.parse_args()

    print(f"Updating dashboard for {args.category}...")

    category_config = load_category_config(args.category)
    keywords_data = load_keywords(args.category)
    geo_codes = load_geo_codes()

    sh = open_category_sheet(args.category)
    trends_data = read_latest_trends(sh)
    volume_data = read_latest_volumes(sh)
    gsc_data = read_latest_gsc(sh)

    print(f"  Trends sections: {len(trends_data)}")
    print(f"  Volume geos: {list(volume_data.keys())}")
    print(f"  GSC weeks: {len(gsc_data)}")

    # 1. Write computed KPIs + city spotlights + signals to Dashboard tab
    write_dashboard_kpis(sh, trends_data, volume_data, gsc_data, keywords_data, geo_codes, category_config)

    # 2. Write city-level summary to City Summary tab
    write_city_summary(sh, trends_data, volume_data, keywords_data, geo_codes, category_config)

    # 3. Write normalized data for Streamlit
    write_dashboard_data(sh, trends_data, volume_data, gsc_data)

    print("\nDashboard update complete.")


if __name__ == "__main__":
    main()
