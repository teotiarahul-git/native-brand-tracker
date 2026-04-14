#!/usr/bin/env python3
"""
Google Search Console branded performance data collector.
Configurable per category via category config.

Usage:
  python3 gsc_collector.py --category instahelp
  python3 gsc_collector.py --category instahelp --days 14 --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(SCRIPT_DIR, "..", ".config")
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import (
    load_category_config, load_keywords,
    open_category_sheet, get_or_create_worksheet
)

INTENT_KEYWORDS = {
    "purchase": ["buy", "amazon", "flipkart", "offer", "discount", "price"],
    "consideration": ["review", "vs ", "compare", "specs"],
    "comparison": ["vs snabbit", "vs pronto", "vs aquaguard", "vs kent", "vs atomberg"],
}


def get_gsc_service():
    """Build Google Search Console API service."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_file = os.path.join(CONFIG_DIR, "token.json")
    if not os.path.exists(token_file):
        print(f"ERROR: No token.json found at {token_file}")
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(token_file)
    return build("searchconsole", "v1", credentials=creds)


def classify_intent(query):
    """Classify a search query into an intent bucket."""
    q = query.lower()
    for kw in INTENT_KEYWORDS["comparison"]:
        if kw in q:
            return "Comparison"
    for kw in INTENT_KEYWORDS["purchase"]:
        if kw in q:
            return "Purchase Intent"
    for kw in INTENT_KEYWORDS["consideration"]:
        if kw in q:
            return "Consideration"
    return "Pure Brand"


def fetch_branded_data(service, site_url, start_date, end_date, branded_filters, page_filters):
    """Fetch branded search performance from GSC."""
    all_queries = {}

    for page_filter in page_filters:
        for brand_filter in branded_filters:
            print(f"  Querying GSC for '{brand_filter}' on page '{page_filter}'...")

            request = {
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "dimensions": ["query"],
                "dimensionFilterGroups": [{
                    "filters": [
                        {"dimension": "query", "operator": "contains", "expression": brand_filter},
                        {"dimension": "page", "operator": "contains", "expression": page_filter},
                        {"dimension": "country", "operator": "equals", "expression": "ind"},
                    ]
                }],
                "rowLimit": 500,
            }

            response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()

            for row in response.get("rows", []):
                query = row["keys"][0]
                key = (query, page_filter)
                if key not in all_queries:
                    all_queries[key] = {
                        "query": query, "page": page_filter,
                        "impressions": 0, "clicks": 0, "position_sum": 0,
                    }
                all_queries[key]["impressions"] = max(all_queries[key]["impressions"], row["impressions"])
                all_queries[key]["clicks"] = max(all_queries[key]["clicks"], row["clicks"])
                all_queries[key]["position_sum"] = max(
                    all_queries[key]["position_sum"], row["position"] * row["impressions"]
                )

    # Flatten to query-level
    query_data = {}
    for key, data in all_queries.items():
        q = data["query"]
        if q not in query_data:
            query_data[q] = {"impressions": 0, "clicks": 0, "position_sum": 0}
        query_data[q]["impressions"] += data["impressions"]
        query_data[q]["clicks"] += data["clicks"]
        query_data[q]["position_sum"] += data["position_sum"]

    return query_data


def aggregate_results(all_queries):
    """Aggregate query-level data into summary metrics."""
    total_impressions = 0
    total_clicks = 0
    weighted_position_sum = 0
    intent_impressions = {"Pure Brand": 0, "Consideration": 0, "Purchase Intent": 0, "Comparison": 0}
    top_query = ("", 0)

    for query, data in all_queries.items():
        impressions = data["impressions"]
        clicks = data["clicks"]

        total_impressions += impressions
        total_clicks += clicks
        weighted_position_sum += data["position_sum"]

        intent = classify_intent(query)
        intent_impressions[intent] += impressions

        if impressions > top_query[1]:
            top_query = (query, impressions)

    avg_position = weighted_position_sum / total_impressions if total_impressions > 0 else 0
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

    return {
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "ctr_pct": round(ctr, 2),
        "avg_position": round(avg_position, 1),
        "pure_brand_impressions": intent_impressions["Pure Brand"],
        "consideration_impressions": intent_impressions["Consideration"],
        "top_query": top_query[0],
        "total_queries": len(all_queries),
    }


def update_google_sheet(category_id, summary, week_start):
    """Update the Google Search Console tab."""
    sh = open_category_sheet(category_id)
    ws = get_or_create_worksheet(sh, "Google Search Console", rows=200, cols=9)

    # Check if headers exist
    existing = ws.get_all_values()
    if not existing or existing[0][0] != "Week_Start":
        headers = [
            "Week_Start", "Total Branded Impressions", "Total Branded Clicks",
            "Click-Through Rate %", "Avg Position", "Pure Brand Impressions",
            "Consideration Impressions", "Top Query This Week", "Notes"
        ]
        ws.update(range_name="A1:I1", values=[headers])
        existing = [headers]

    week_str = week_start.strftime("%Y-%m-%d")
    row_num = None
    for i, row in enumerate(existing):
        if row and row[0] == week_str:
            row_num = i + 1
            break
    if row_num is None:
        row_num = len(existing) + 1

    row_data = [
        week_str,
        summary["total_impressions"],
        summary["total_clicks"],
        summary["ctr_pct"],
        summary["avg_position"],
        summary["pure_brand_impressions"],
        summary["consideration_impressions"],
        summary["top_query"],
        f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    ws.update(range_name=f"A{row_num}:I{row_num}", values=[row_data])
    print(f"  Google Search Console tab updated: row {row_num} for week {week_str}")


def main():
    parser = argparse.ArgumentParser(description="Collect GSC branded performance data")
    parser.add_argument("--category", required=True, help="Category ID")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Print without updating sheet")
    args = parser.parse_args()

    category_config = load_category_config(args.category)
    site_url = category_config.get("gsc_site_url", "")
    branded_filters = category_config.get("gsc_branded_filters", [])
    page_filters = category_config.get("gsc_page_filters", [])

    if not site_url:
        print("ERROR: gsc_site_url not set in category config")
        sys.exit(1)

    end_date = date.today() - timedelta(days=3)
    start_date = end_date - timedelta(days=args.days)
    week_start = start_date - timedelta(days=start_date.weekday())

    print(f"Collecting Google Search Console data for {category_config['display_name']}...")
    print(f"  Site: {site_url}")
    print(f"  Period: {start_date} to {end_date}")

    service = get_gsc_service()
    all_queries = fetch_branded_data(service, site_url, start_date, end_date, branded_filters, page_filters)
    summary = aggregate_results(all_queries)

    print(f"\n=== Google Search Console Summary (Week of {week_start}) ===")
    print(f"  Total Branded Impressions: {summary['total_impressions']:,}")
    print(f"  Total Branded Clicks: {summary['total_clicks']:,}")
    print(f"  Click-Through Rate: {summary['ctr_pct']}%")
    print(f"  Avg Position: {summary['avg_position']}")
    print(f"  Top Query: {summary['top_query']}")

    output = {"week_start": week_start.strftime("%Y-%m-%d"), **summary}
    print(f"\n__JSON_OUTPUT__:{json.dumps(output)}")

    if not args.dry_run:
        update_google_sheet(args.category, summary, week_start)

    return output


if __name__ == "__main__":
    main()
