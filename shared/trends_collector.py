#!/usr/bin/env python3
"""
City-aware Google Trends data collector.
Collects weekly indexed searches (0-100) for all configured geos.

Usage:
  python3 trends_collector.py --category instahelp
  python3 trends_collector.py --category instahelp --geo delhi
  python3 trends_collector.py --category instahelp --timeframe '2026-01-01 2026-04-01' --dry-run
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import (
    load_category_config, load_keywords, load_geo_codes,
    open_category_sheet, get_or_create_worksheet
)


def fetch_trends_data(terms, timeframe="today 3-m", geo="IN"):
    """
    Fetch Google Trends interest-over-time data.
    Returns a pandas DataFrame with weekly index values (0-100).
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=330)  # IST

    print(f"  Fetching: {terms}")
    print(f"  Timeframe: {timeframe}, Geo: {geo}")

    pytrends.build_payload(terms, cat=0, timeframe=timeframe, geo=geo)
    time.sleep(3)  # Rate limit

    df = pytrends.interest_over_time()

    if df.empty:
        print("  WARNING: No data returned from Google Trends.")
        return None

    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])

    return df


def collect_trends_for_geo(keywords_data, timeframe, geo_code):
    """Collect trends for both comparison sets for a single geo."""
    trends_sets = keywords_data["trends_sets"]
    results = {}

    for set_key, set_info in trends_sets.items():
        label = set_info["label"]
        terms = set_info["terms"]

        print(f"\n--- {label} (Geo: {geo_code}) ---")

        try:
            df = fetch_trends_data(terms, timeframe=timeframe, geo=geo_code)
            if df is not None:
                weekly_data = []
                for idx, row in df.iterrows():
                    week_start = idx.strftime("%Y-%m-%d")
                    indices = {term: int(row[term]) for term in terms}
                    weekly_data.append({
                        "week_start": week_start,
                        "indices": indices,
                    })

                latest = weekly_data[-1] if weekly_data else {}
                results[set_key] = {
                    "label": label,
                    "terms": terms,
                    "weekly_data": weekly_data,
                    "latest": latest,
                    "source": "pytrends",
                }

                if latest:
                    print(f"  Latest week ({latest['week_start']}):")
                    for term in terms:
                        idx_val = latest["indices"].get(term, 0)
                        print(f"    {term}: index={idx_val}")
            else:
                results[set_key] = {
                    "label": label, "terms": terms,
                    "weekly_data": [], "latest": {},
                    "source": "pytrends", "error": "No data returned",
                }
        except Exception as e:
            print(f"  ERROR: pytrends failed — {e}")
            results[set_key] = {
                "label": label, "terms": terms,
                "weekly_data": [], "latest": {},
                "source": "failed", "error": str(e),
            }

    return results


def collect_all_trends(category_config, keywords_data, timeframe, target_geo=None):
    """Collect trends for all configured geos (or a single target geo)."""
    geo_codes = load_geo_codes()
    configured_geos = category_config.get("geos", ["india"])

    if target_geo:
        configured_geos = [target_geo]

    # Deduplicate Trends geo codes (Mumbai and Pune share IN-MH)
    seen_trends_geos = {}
    geo_results = {}

    for geo_name in configured_geos:
        geo_info = geo_codes.get(geo_name)
        if not geo_info:
            print(f"WARNING: Unknown geo '{geo_name}', skipping.")
            continue

        trends_geo = geo_info["trends_geo"]
        label = geo_info["label"]

        # Skip duplicate Trends geos (e.g., Pune uses same IN-MH as Mumbai)
        if trends_geo in seen_trends_geos:
            print(f"\n=== Skipping {label} (same Trends geo {trends_geo} as {seen_trends_geos[trends_geo]}) ===")
            # Copy results from the duplicate
            geo_results[geo_name] = geo_results[seen_trends_geos[trends_geo]].copy()
            geo_results[geo_name]["label"] = f"{label} (same as {seen_trends_geos[trends_geo]})"
            geo_results[geo_name]["shared_trends_geo"] = True
            continue

        seen_trends_geos[trends_geo] = geo_name

        print(f"\n{'='*60}")
        print(f"=== {label} ({trends_geo}) ===")
        print(f"{'='*60}")

        results = collect_trends_for_geo(keywords_data, timeframe, trends_geo)
        geo_results[geo_name] = {
            "geo": geo_name,
            "trends_geo": trends_geo,
            "label": label,
            "sets": results,
            "shared_trends_geo": False,
        }

    return geo_results


def update_google_sheet(category_id, geo_results):
    """Update the Trends Indexed Searches tab in Google Sheets."""
    sh = open_category_sheet(category_id)
    ws = get_or_create_worksheet(sh, "Trends Indexed Searches", rows=2000, cols=12)

    all_rows = [["Google Trends — Weekly Indexed Searches (0-100)"], [""]]

    for geo_name, geo_data in geo_results.items():
        label = geo_data["label"]
        sets = geo_data.get("sets", {})

        for set_key, set_data in sets.items():
            set_label = set_data.get("label", set_key)
            terms = set_data.get("terms", [])
            weekly = set_data.get("weekly_data", [])

            all_rows.append([f"=== {label} — {set_label} ==="])
            all_rows.append(["Week_Start"] + terms + ["Notes"])

            for week in weekly:
                row = [week["week_start"]]
                for term in terms:
                    row.append(week["indices"].get(term, 0))
                row.append("")
                all_rows.append(row)

            all_rows.append([""])
            all_rows.append([""])

    # Pad rows and write
    max_cols = max(len(r) for r in all_rows) if all_rows else 1
    all_rows = [r + [""] * (max_cols - len(r)) for r in all_rows]

    # Sanitize NaN/Inf
    for i, row in enumerate(all_rows):
        for j, val in enumerate(row):
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                all_rows[i][j] = 0

    end_col = chr(64 + min(max_cols, 26))
    ws.update(range_name=f"A1:{end_col}{len(all_rows)}", values=all_rows)
    print(f"\n  Trends Indexed Searches tab updated ({len(all_rows)} rows).")


def main():
    parser = argparse.ArgumentParser(description="Collect Google Trends indexed searches")
    parser.add_argument("--category", required=True, help="Category ID (e.g., instahelp)")
    parser.add_argument("--geo", help="Single geo to collect (e.g., delhi)")
    parser.add_argument("--timeframe", default="today 3-m", help="Pytrends timeframe")
    parser.add_argument("--dry-run", action="store_true", help="Print without updating sheet")
    args = parser.parse_args()

    category_config = load_category_config(args.category)
    keywords_data = load_keywords(args.category)

    print(f"Collecting Google Trends data for {category_config['display_name']}...")
    geo_results = collect_all_trends(category_config, keywords_data, args.timeframe, args.geo)

    # Print summary
    print(f"\n{'='*60}")
    print("=== Collection Summary ===")
    for geo_name, geo_data in geo_results.items():
        label = geo_data["label"]
        sets = geo_data.get("sets", {})
        for set_key, set_data in sets.items():
            latest = set_data.get("latest", {})
            if latest:
                print(f"\n  {label} — {set_data['label']}:")
                print(f"    Week: {latest.get('week_start', 'N/A')}")
                for term, idx_val in latest.get("indices", {}).items():
                    print(f"      {term}: {idx_val}")

    # JSON output
    output = {
        "collected_at": datetime.now().isoformat(),
        "category": args.category,
        "timeframe": args.timeframe,
        "geos_collected": list(geo_results.keys()),
    }
    print(f"\n__JSON_OUTPUT__:{json.dumps(output)}")

    if not args.dry_run:
        update_google_sheet(args.category, geo_results)

    return geo_results


if __name__ == "__main__":
    main()
