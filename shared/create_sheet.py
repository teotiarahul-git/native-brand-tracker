#!/usr/bin/env python3
"""
Create a Google Sheet for a category tracker with all tabs pre-configured.
Run once during setup for each new category.

Usage: python3 create_sheet.py --category instahelp
"""

import argparse
import json
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import (
    get_sheets_client, load_category_config, save_category_config,
    load_keywords, load_geo_codes
)


def create_tracker_sheet(category_id):
    config = load_category_config(category_id)
    keywords_data = load_keywords(category_id)
    geo_codes = load_geo_codes()

    display_name = config["display_name"]
    brand_keys = list(keywords_data["brands"].keys())
    brand_names = [keywords_data["brands"][k]["display_name"] for k in brand_keys]
    configured_geos = config.get("geos", ["india"])

    gc = get_sheets_client()
    title = f"{display_name} — Brand Awareness Tracker"

    print(f"Creating Google Sheet: '{title}'...")
    sh = gc.create(title)
    sheet_id = sh.id
    sheet_url = sh.url
    print(f"  Sheet ID: {sheet_id}")
    print(f"  URL: {sheet_url}")

    # --- Tab 1: Dashboard ---
    ws = sh.sheet1
    ws.update_title("Dashboard")
    rows = [
        [f"{display_name} — Brand Awareness Tracker"],
        [f"Coverage: {', '.join(geo_codes.get(g, {}).get('label', g) for g in configured_geos)}"],
        ["Sources: Google Trends (weekly indexed searches) · Google Ads Keyword Planner (monthly volumes) · Google Search Console"],
        [""],
        ["--- All India Summary ---"],
        ["Metric", "Latest Value", "Previous", "Week-over-Week Change", "Notes"],
    ]
    # Add KPI rows for each brand
    for bn in brand_names:
        rows.append([f"{bn} — Indexed Searches (Google Trends)", "", "", "", ""])
    rows.append([""])
    for bn in brand_names:
        rows.append([f"{bn} — Monthly Search Volume (Google Ads)", "", "", "", ""])
    rows.append([""])
    rows.append(["Branded Impressions (Google Search Console)", "", "", "", ""])
    rows.append(["Branded Clicks (Google Search Console)", "", "", "", ""])
    rows.append(["Click-Through Rate % (Google Search Console)", "", "", "", ""])
    rows.append([""])
    rows.append(["--- Active Signals ---"])
    rows.append(["Signal", "What It Means", "Recommended Action"])

    max_cols = max(len(r) for r in rows)
    rows = [r + [""] * (max_cols - len(r)) for r in rows]
    end_col = chr(64 + max_cols)
    ws.update(range_name=f"A1:{end_col}{len(rows)}", values=rows)
    print("  Dashboard tab created.")

    # --- Tab 2: Trends Indexed Searches ---
    ws2 = sh.add_worksheet("Trends Indexed Searches", rows=2000, cols=12)
    trends_rows = [["Google Trends — Weekly Indexed Searches (0-100)"], [""]]

    for geo_name in configured_geos:
        geo_info = geo_codes.get(geo_name, {"label": geo_name})
        label = geo_info["label"]

        for set_key, set_data in keywords_data["trends_sets"].items():
            set_label = set_data["label"]
            terms = set_data["terms"]
            trends_rows.append([f"=== {label} — {set_label} ==="])
            trends_rows.append(["Week_Start"] + terms + ["Notes"])
            trends_rows.append([""])  # Data rows will be filled by collector
            trends_rows.append([""])

    max_cols = max(len(r) for r in trends_rows)
    trends_rows = [r + [""] * (max_cols - len(r)) for r in trends_rows]
    end_col = chr(64 + max_cols)
    ws2.update(range_name=f"A1:{end_col}{len(trends_rows)}", values=trends_rows)
    print("  Trends Indexed Searches tab created.")

    # --- Tab 3: Monthly Search Volume ---
    ws3 = sh.add_worksheet("Monthly Search Volume", rows=500, cols=15)
    vol_rows = [["Monthly Search Volume — Google Ads Keyword Planner"], [""]]

    for geo_name in configured_geos:
        geo_info = geo_codes.get(geo_name, {"label": geo_name})
        label = geo_info["label"]
        vol_rows.append([f"=== {label} ==="])
        header = ["Month"] + [f"{n} Volume" for n in brand_names] + ["Category Baseline", "Total Market", "Notes"]
        vol_rows.append(header)
        vol_rows.append([""])
        vol_rows.append([""])

    max_cols = max(len(r) for r in vol_rows)
    vol_rows = [r + [""] * (max_cols - len(r)) for r in vol_rows]
    end_col = chr(64 + max_cols)
    ws3.update(range_name=f"A1:{end_col}{len(vol_rows)}", values=vol_rows)
    print("  Monthly Search Volume tab created.")

    # --- Tab 4: Google Search Console ---
    ws4 = sh.add_worksheet("Google Search Console", rows=200, cols=9)
    gsc_headers = [
        "Week_Start", "Total Branded Impressions", "Total Branded Clicks",
        "Click-Through Rate %", "Avg Position", "Pure Brand Impressions",
        "Consideration Impressions", "Top Query This Week", "Notes"
    ]
    ws4.update(range_name="A1:I1", values=[gsc_headers])
    print("  Google Search Console tab created.")

    # --- Tab 5: City Summary ---
    ws5 = sh.add_worksheet("City Summary", rows=20, cols=12)
    city_header = ["City"] + [f"{n} Index" for n in brand_names] + [f"{n} Volume" for n in brand_names] + ["Week-over-Week Trend"]
    ws5.update(range_name=f"A1:{chr(64 + len(city_header))}1", values=[city_header])
    # Pre-fill city names
    for i, geo_name in enumerate(configured_geos):
        geo_info = geo_codes.get(geo_name, {"label": geo_name})
        ws5.update(range_name=f"A{i + 2}", values=[[geo_info["label"]]])
    print("  City Summary tab created.")

    # --- Tab 6: Keywords ---
    ws6 = sh.add_worksheet("Keywords", rows=200, cols=3)
    kw_rows = [["Keyword", "Intent", "Status"]]

    for brand_key, brand_info in keywords_data["brands"].items():
        kw_rows.append([f"=== {brand_info['display_name']} ===", "", ""])
        for kw in brand_info["include"]:
            intent = "Awareness"
            kw_lower = kw.lower()
            if any(w in kw_lower for w in ["buy", "amazon", "flipkart", "price"]):
                intent = "Purchase / Price"
            elif any(w in kw_lower for w in ["review", "vs "]):
                intent = "Consideration"
            kw_rows.append([kw, intent, "Include"])
        for kw in brand_info["exclude"]:
            kw_rows.append([kw, "Noise / Disambiguation", "Exclude"])
        kw_rows.append(["", "", ""])

    kw_rows.append(["=== Category Baseline (Unbranded) ===", "", ""])
    for kw in keywords_data["category_baseline"]:
        kw_rows.append([kw, "Unbranded / Generic", "Baseline"])

    ws6.update(range_name=f"A1:C{len(kw_rows)}", values=kw_rows)
    print("  Keywords tab created.")

    # --- Tab 7: Dashboard Data (normalized for Streamlit) ---
    ws7 = sh.add_worksheet("Dashboard Data", rows=5000, cols=6)
    ws7.update(range_name="A1:F1", values=[["Date", "Geo", "Source", "Brand", "Metric", "Value"]])
    print("  Dashboard Data tab created.")

    # Update category config with sheet ID
    config["google_sheet_id"] = sheet_id
    config["google_sheet_url"] = sheet_url
    save_category_config(category_id, config)
    print(f"\n  Category config updated with sheet ID and URL.")

    return sheet_id, sheet_url


def main():
    parser = argparse.ArgumentParser(description="Create category tracking Google Sheet")
    parser.add_argument("--category", required=True, help="Category ID (e.g., instahelp)")
    args = parser.parse_args()

    sheet_id, sheet_url = create_tracker_sheet(args.category)

    print(f"\n=== Sheet Created ===")
    print(f"  Category: {args.category}")
    print(f"  ID: {sheet_id}")
    print(f"  URL: {sheet_url}")
    print(f"\nNext: Run trends_collector.py, keyword_volume_collector.py, or gsc_collector.py")


if __name__ == "__main__":
    main()
