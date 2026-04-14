#!/usr/bin/env python3
"""
City-aware Google Ads Keyword Planner volume collector.
Collects monthly search volumes (absolute) for all configured geos.

Usage:
  python3 keyword_volume_collector.py --category instahelp
  python3 keyword_volume_collector.py --category instahelp --geo delhi --month 2026-03
  python3 keyword_volume_collector.py --category instahelp --dry-run
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(SCRIPT_DIR, "..", ".config")
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import (
    load_category_config, load_keywords, load_geo_codes,
    open_category_sheet, get_or_create_worksheet
)


def get_google_ads_client():
    """Initialize Google Ads API client."""
    from google.ads.googleads.client import GoogleAdsClient

    yaml_path = os.path.join(CONFIG_DIR, "google-ads.yaml")
    if not os.path.exists(yaml_path):
        print(f"ERROR: Google Ads config not found at {yaml_path}")
        sys.exit(1)

    return GoogleAdsClient.load_from_storage(yaml_path)


def fetch_keyword_volumes(client, customer_id, keywords, geo_criterion_id=2356):
    """
    Fetch monthly search volumes for keywords using Keyword Planner API.
    geo_criterion_id: 2356=India, or city-specific IDs from geo_codes.json
    Returns: dict of {keyword: avg_monthly_searches}
    """
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = customer_id
    request.keywords.extend(keywords)

    # Set geo target
    request.geo_target_constants.append(
        client.get_service("GeoTargetConstantService").geo_target_constant_path(geo_criterion_id)
    )
    # Language: English
    request.language = client.get_service("GoogleAdsService").language_constant_path(1000)

    response = keyword_plan_idea_service.generate_keyword_historical_metrics(request=request)

    volumes = {}
    for result in response.results:
        kw = result.text
        metrics = result.keyword_metrics
        if metrics and metrics.avg_monthly_searches:
            volumes[kw] = metrics.avg_monthly_searches
        else:
            volumes[kw] = 0

    return volumes


def collect_brand_volumes_for_geo(client, customer_id, keywords_data, geo_criterion_id, geo_label):
    """Collect volumes for all brands + category baseline for a single geo."""
    results = {}

    for brand_key, brand_info in keywords_data["brands"].items():
        include_kws = brand_info["include"]
        exclude_set = set(kw.lower() for kw in brand_info["exclude"])

        print(f"  [{geo_label}] Fetching volumes for {brand_info['display_name']}...")
        time.sleep(5)  # Rate limit

        volumes = fetch_keyword_volumes(client, customer_id, include_kws, geo_criterion_id)

        # Filter out excluded patterns
        filtered_total = 0
        for kw, vol in volumes.items():
            if not any(exc in kw.lower() for exc in exclude_set):
                filtered_total += vol

        results[brand_key] = {
            "display_name": brand_info["display_name"],
            "total_volume": filtered_total,
            "keyword_volumes": volumes,
        }
        print(f"    Total: {filtered_total:,}")

    # Category baseline
    print(f"  [{geo_label}] Fetching category baseline volumes...")
    time.sleep(5)
    baseline_kws = keywords_data["category_baseline"]
    baseline_volumes = fetch_keyword_volumes(client, customer_id, baseline_kws, geo_criterion_id)
    baseline_total = sum(baseline_volumes.values())
    results["category_baseline"] = {
        "display_name": "Category Baseline (Unbranded)",
        "total_volume": baseline_total,
        "keyword_volumes": baseline_volumes,
    }
    print(f"    Total: {baseline_total:,}")

    return results


def collect_all_volumes(category_config, keywords_data, target_geo=None):
    """Collect volumes for all configured geos."""
    geo_codes = load_geo_codes()
    configured_geos = category_config.get("geos", ["india"])
    customer_id = category_config["google_ads_customer_id"]

    if target_geo:
        configured_geos = [target_geo]

    client = get_google_ads_client()
    all_geo_results = {}

    for geo_name in configured_geos:
        geo_info = geo_codes.get(geo_name)
        if not geo_info:
            print(f"WARNING: Unknown geo '{geo_name}', skipping.")
            continue

        criterion_id = geo_info["ads_criterion_id"]
        label = geo_info["label"]

        print(f"\n{'='*60}")
        print(f"=== {label} (Criterion ID: {criterion_id}) ===")
        print(f"{'='*60}")

        results = collect_brand_volumes_for_geo(client, customer_id, keywords_data, criterion_id, label)
        total_market = sum(r["total_volume"] for r in results.values())

        all_geo_results[geo_name] = {
            "geo": geo_name,
            "label": label,
            "criterion_id": criterion_id,
            "brands": results,
            "total_market": total_market,
        }

    return all_geo_results


def update_google_sheet(category_id, all_geo_results, target_month, keywords_data):
    """Update the Monthly Search Volume tab in Google Sheets."""
    sh = open_category_sheet(category_id)
    ws = get_or_create_worksheet(sh, "Monthly Search Volume", rows=500, cols=15)

    brand_keys = list(keywords_data["brands"].keys())
    brand_names = [keywords_data["brands"][k]["display_name"] for k in brand_keys]
    month_str = target_month.strftime("%Y-%m")

    all_rows = [["Monthly Search Volume — Google Ads Keyword Planner"], [""]]

    for geo_name, geo_data in all_geo_results.items():
        label = geo_data["label"]
        brands = geo_data["brands"]
        total_market = geo_data["total_market"]

        all_rows.append([f"=== {label} ==="])
        header = ["Month"] + [f"{n} Volume" for n in brand_names] + ["Category Baseline", "Total Market", "Notes"]
        all_rows.append(header)

        row = [month_str]
        for bk in brand_keys:
            row.append(brands.get(bk, {}).get("total_volume", 0))
        row.append(brands.get("category_baseline", {}).get("total_volume", 0))
        row.append(total_market)
        row.append(f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        all_rows.append(row)

        all_rows.append([""])
        all_rows.append([""])

    max_cols = max(len(r) for r in all_rows) if all_rows else 1
    all_rows = [r + [""] * (max_cols - len(r)) for r in all_rows]

    end_col = chr(64 + min(max_cols, 26))
    ws.update(range_name=f"A1:{end_col}{len(all_rows)}", values=all_rows)
    print(f"\n  Monthly Search Volume tab updated ({len(all_rows)} rows).")


def main():
    parser = argparse.ArgumentParser(description="Collect keyword volumes from Google Ads")
    parser.add_argument("--category", required=True, help="Category ID")
    parser.add_argument("--geo", help="Single geo to collect")
    parser.add_argument("--month", help="Target month YYYY-MM (default: last completed month)")
    parser.add_argument("--dry-run", action="store_true", help="Print without updating sheet")
    args = parser.parse_args()

    if args.month:
        target_month = datetime.strptime(args.month, "%Y-%m").date()
    else:
        today = date.today()
        target_month = date(today.year, today.month, 1) if today.day > 15 else date(
            today.year if today.month > 1 else today.year - 1,
            today.month - 1 if today.month > 1 else 12, 1
        )

    category_config = load_category_config(args.category)
    keywords_data = load_keywords(args.category)

    print(f"Collecting keyword volumes for {category_config['display_name']}...")
    print(f"  Target month: {target_month.strftime('%Y-%m')}")

    all_geo_results = collect_all_volumes(category_config, keywords_data, args.geo)

    # Print summary
    print(f"\n{'='*60}")
    print(f"=== Volume Summary ({target_month.strftime('%Y-%m')}) ===")
    for geo_name, geo_data in all_geo_results.items():
        label = geo_data["label"]
        brands = geo_data["brands"]
        print(f"\n  {label}:")
        for bk, bv in brands.items():
            print(f"    {bv['display_name']}: {bv['total_volume']:,}")

    output = {
        "month": target_month.strftime("%Y-%m"),
        "category": args.category,
        "geos_collected": list(all_geo_results.keys()),
    }
    print(f"\n__JSON_OUTPUT__:{json.dumps(output)}")

    if not args.dry_run:
        update_google_sheet(args.category, all_geo_results, target_month, keywords_data)

    return all_geo_results


if __name__ == "__main__":
    main()
