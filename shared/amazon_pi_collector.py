#!/usr/bin/env python3
"""
Amazon Pi data collector — reads extracted ECharts JSON and pushes to Google Sheets.

Amazon Pi (pi.amazon.in) has no API. Data is extracted via Chrome browser automation
(JavaScript extracts ECharts dataset from the DOM, saves as JSON). This script reads
that JSON and writes Brand Recall + Ad Share of Voice data to Google Sheets.

Brand Recall Rebasing:
  Pi's indexed values change baseline each time you pull a different date range.
  E.g., Oct'24 = 100 in a Oct'24–Mar'26 pull, but Oct'24 = 150 in the older
  Apr'24–Oct'25 pull. The collector resolves this by:
    1. Treating the newest extraction as the primary baseline.
    2. Finding overlap months between primary and older extractions.
    3. Computing a scale factor from overlaps and rebasing older data.
    4. The key metric (Native / Competitor Average) is baseline-independent.

Usage:
  python3 amazon_pi_collector.py --category native --data-dir data/amazon_pi
  python3 amazon_pi_collector.py --category native --data-file data/amazon_pi/monthly_extract_full.json
  python3 amazon_pi_collector.py --category native --data-dir data/amazon_pi --dry-run
"""

import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import (
    load_category_config,
    open_category_sheet,
    get_or_create_worksheet,
)

# ---------- Month abbreviation mapping ----------
MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


# ------------------------------------------------------------------ #
#  Date normalisation helpers
# ------------------------------------------------------------------ #

def parse_monthly_timestamp(ts):
    """Convert "Oct'24" or "Oct '24" -> "2024-10", "Mar'26" or "Mar '26" -> "2026-03"."""
    m = re.match(r"([A-Za-z]{3})\s*'(\d{2})$", ts.strip())
    if not m:
        raise ValueError(f"Cannot parse monthly timestamp: {ts}")
    month_num = MONTH_ABBR[m.group(1)]
    year = 2000 + int(m.group(2))
    return f"{year:04d}-{month_num:02d}"


def parse_daily_timestamp(ts, reference_date):
    """
    Convert "30-Mar" -> "2026-03-30" using reference_date for year inference.
    """
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})$", ts)
    if not m:
        raise ValueError(f"Cannot parse daily timestamp: {ts}")
    day = int(m.group(1))
    month_num = MONTH_ABBR[m.group(2)]
    year = reference_date.year

    if month_num > reference_date.month + 1:
        year -= 1

    return f"{year:04d}-{month_num:02d}-{day:02d}"


def monday_of(date_str):
    """Return the Monday (ISO week start) for a YYYY-MM-DD date string."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


# ------------------------------------------------------------------ #
#  Weekly aggregation
# ------------------------------------------------------------------ #

def aggregate_daily_to_weekly(rows, value_columns):
    """
    rows: list of dicts with 'date' (YYYY-MM-DD) + value_columns keys.
    Returns list of dicts with 'week_start' + averaged value_columns, sorted.
    """
    weeks = defaultdict(lambda: defaultdict(list))

    for row in rows:
        ws = monday_of(row["date"])
        for col in value_columns:
            val = row.get(col)
            if val is not None:
                weeks[ws][col].append(val)

    result = []
    for ws in sorted(weeks.keys()):
        entry = {"week_start": ws}
        for col in value_columns:
            vals = weeks[ws][col]
            entry[col] = round(sum(vals) / len(vals), 2) if vals else 0
        result.append(entry)

    return result


# ------------------------------------------------------------------ #
#  NaN/Inf sanitisation
# ------------------------------------------------------------------ #

def sanitize_rows(rows):
    """Replace NaN/Inf with 0 in a 2D list."""
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                rows[i][j] = 0
    return rows


# ------------------------------------------------------------------ #
#  Competitor mapping from category config
# ------------------------------------------------------------------ #

def get_competitor_labels(category_config):
    """
    Read amazon_pi.competitor_mapping from category config.
    Defaults: Rank 1 = Aquaguard, Rank 2 = Kent, Rank 3 = Unknown.
    """
    pi_config = category_config.get("amazon_pi", {})
    mapping = pi_config.get("competitor_mapping", {})
    return {
        "rank_1": mapping.get("rank_1", "Aquaguard"),
        "rank_2": mapping.get("rank_2", "Kent"),
        "rank_3": mapping.get("rank_3", "Unknown"),
    }


# ------------------------------------------------------------------ #
#  Sheet read / merge helpers
# ------------------------------------------------------------------ #

DATA_START_ROW = 5  # Row 5 onwards is data (1-indexed)


def read_existing_data(ws):
    """Read existing data rows (row 5+) from a worksheet. Returns list of lists."""
    all_values = ws.get_all_values()
    if len(all_values) < DATA_START_ROW:
        return []
    return all_values[DATA_START_ROW - 1:]


def merge_data_rows(existing_rows, new_rows, date_col=0):
    """
    Upsert: overwrite rows with matching date key, append new ones.
    Returns merged list sorted by date key.
    """
    by_date = {}
    for row in existing_rows:
        if row and row[date_col]:
            by_date[row[date_col]] = row
    for row in new_rows:
        if row and row[date_col]:
            by_date[row[date_col]] = row
    return [by_date[k] for k in sorted(by_date.keys())]


# ------------------------------------------------------------------ #
#  Brand Recall: rebasing across different Pi extractions
# ------------------------------------------------------------------ #

def load_all_brand_recall_monthly(data_dir, reference_date):
    """
    Load all JSON files with monthly brand_recall data from data_dir.
    Returns list of (extracted_at_dt, {date: {your_brand, competitor_avg}}) sorted
    newest-first.
    """
    datasets = []
    json_files = glob.glob(os.path.join(data_dir, "*.json"))

    for fpath in json_files:
        with open(fpath) as f:
            pi_data = json.load(f)

        if pi_data.get("view") != "monthly":
            continue
        if "brand_recall" not in pi_data:
            continue

        extracted_at = pi_data.get("extracted_at", "2020-01-01T00:00:00")
        extracted_dt = datetime.fromisoformat(extracted_at)

        by_month = {}
        for row in pi_data["brand_recall"]["source"]:
            ts_raw = row[0]
            date_key = parse_monthly_timestamp(ts_raw)
            by_month[date_key] = {
                "your_brand": row[1] if len(row) > 1 else 0,
                "competitor_avg": row[2] if len(row) > 2 else 0,
            }

        datasets.append((extracted_dt, fpath, by_month))
        print(f"    Loaded {os.path.basename(fpath)}: {len(by_month)} months "
              f"({min(by_month.keys())} to {max(by_month.keys())})")

    # Sort newest first — newest extraction is the primary baseline
    datasets.sort(key=lambda x: x[0], reverse=True)
    return datasets


def rebase_brand_recall(datasets):
    """
    Rebase all datasets to the newest extraction's index scale.

    Algorithm:
      1. Primary = newest extraction. Its values are used as-is.
      2. For each older extraction (in order):
         a. Find overlap months with the already-merged data.
         b. Compute scale_native = avg(primary[m].native / older[m].native)
            and scale_comp  = avg(primary[m].comp   / older[m].comp)
         c. For months only in the older set, multiply by scale factors.
         d. Add those rebased months to the merged set.

    Returns dict {date_key: {your_brand, competitor_avg, ratio}} sorted by date.
    """
    if not datasets:
        return {}

    # Start with the primary (newest) dataset
    primary_dt, primary_path, primary_data = datasets[0]
    merged = {}
    for date_key, vals in primary_data.items():
        yb = vals["your_brand"]
        ca = vals["competitor_avg"]
        pct = round(yb / ca * 100, 2) if ca else 0
        merged[date_key] = {
            "your_brand": yb,
            "competitor_avg": ca,
            "pct": pct,
        }

    print(f"    Primary baseline: {os.path.basename(primary_path)} "
          f"({len(merged)} months)")

    # Merge older datasets with rebasing
    for older_dt, older_path, older_data in datasets[1:]:
        # Find overlap months
        overlap_months = set(merged.keys()) & set(older_data.keys())
        if not overlap_months:
            print(f"    WARNING: No overlap with {os.path.basename(older_path)}, "
                  f"skipping (cannot rebase)")
            continue

        # Compute scale factors from overlap
        scale_native_samples = []
        scale_comp_samples = []
        for m in sorted(overlap_months):
            m_new = merged[m]
            m_old = older_data[m]
            if m_old["your_brand"] > 0:
                scale_native_samples.append(m_new["your_brand"] / m_old["your_brand"])
            if m_old["competitor_avg"] > 0:
                scale_comp_samples.append(m_new["competitor_avg"] / m_old["competitor_avg"])

        if not scale_native_samples or not scale_comp_samples:
            print(f"    WARNING: Zero values in overlap with "
                  f"{os.path.basename(older_path)}, skipping")
            continue

        scale_native = sum(scale_native_samples) / len(scale_native_samples)
        scale_comp = sum(scale_comp_samples) / len(scale_comp_samples)

        print(f"    Rebasing {os.path.basename(older_path)}: "
              f"{len(overlap_months)} overlap months, "
              f"scale_native={scale_native:.4f}, scale_comp={scale_comp:.4f}")

        # Add months from older dataset that are NOT in merged yet
        added = 0
        for date_key, vals in older_data.items():
            if date_key in merged:
                continue  # Primary data wins for overlap months
            yb_rebased = round(vals["your_brand"] * scale_native, 1)
            ca_rebased = round(vals["competitor_avg"] * scale_comp, 1)
            pct = round(vals["your_brand"] / vals["competitor_avg"] * 100, 2) \
                if vals["competitor_avg"] else 0
            merged[date_key] = {
                "your_brand": yb_rebased,
                "competitor_avg": ca_rebased,
                "pct": pct,
            }
            added += 1

        print(f"    Added {added} earlier months from {os.path.basename(older_path)}")

    return merged


def build_brand_recall_rows(merged_data):
    """
    Build sheet rows from rebased+merged brand recall data.
    Each row: [date_key, Native (Rebased Index), Competitor Average (Rebased Index),
               Native search (%) vs Competitor average, Notes]
    """
    rows = []
    for date_key in sorted(merged_data.keys()):
        entry = merged_data[date_key]
        yb = entry["your_brand"]
        ca = entry["competitor_avg"]
        pct = entry["pct"]
        rows.append([date_key, yb, ca, pct, ""])
    return rows


# ------------------------------------------------------------------ #
#  Brand Recall processing (single-file, for daily/weekly)
# ------------------------------------------------------------------ #

def process_brand_recall(data, view, reference_date):
    """
    Process brand_recall section -> list of dicts with normalised dates.
    """
    source = data["source"]
    parsed = []
    for row in source:
        ts_raw = row[0]
        your_brand = row[1] if len(row) > 1 else 0
        comp_avg = row[2] if len(row) > 2 else 0

        if view == "monthly":
            date_key = parse_monthly_timestamp(ts_raw)
        else:
            date_key = parse_daily_timestamp(ts_raw, reference_date)

        parsed.append({
            "date": date_key,
            "your_brand": your_brand,
            "competitor_avg": comp_avg,
        })

    return parsed


def load_all_brand_recall_daily(data_dir, reference_date):
    """
    Load all JSON files with daily brand_recall data from data_dir.
    Returns list of (extracted_at_dt, fpath, {date: {your_brand, competitor_avg}})
    sorted newest-first.
    """
    datasets = []
    json_files = glob.glob(os.path.join(data_dir, "*.json"))

    for fpath in json_files:
        with open(fpath) as f:
            pi_data = json.load(f)

        if pi_data.get("view") != "daily":
            continue
        if "brand_recall" not in pi_data:
            continue

        extracted_at = pi_data.get("extracted_at", "2020-01-01T00:00:00")
        extracted_dt = datetime.fromisoformat(extracted_at)

        by_date = {}
        for row in pi_data["brand_recall"]["source"]:
            ts_raw = row[0]
            date_key = parse_daily_timestamp(ts_raw, extracted_dt)
            by_date[date_key] = {
                "your_brand": row[1] if len(row) > 1 else 0,
                "competitor_avg": row[2] if len(row) > 2 else 0,
            }

        datasets.append((extracted_dt, fpath, by_date))
        print(f"    Loaded {os.path.basename(fpath)}: {len(by_date)} days "
              f"({min(by_date.keys())} to {max(by_date.keys())})")

    datasets.sort(key=lambda x: x[0], reverse=True)
    return datasets


def rebase_brand_recall_daily(datasets):
    """
    Rebase daily brand recall across extractions, same logic as monthly.
    Returns dict {date_key: {your_brand, competitor_avg, pct}}.
    """
    if not datasets:
        return {}

    primary_dt, primary_path, primary_data = datasets[0]
    merged = {}
    for date_key, vals in primary_data.items():
        yb = vals["your_brand"]
        ca = vals["competitor_avg"]
        pct = round(yb / ca * 100, 2) if ca else 0
        merged[date_key] = {"your_brand": yb, "competitor_avg": ca, "pct": pct}

    print(f"    Primary baseline: {os.path.basename(primary_path)} "
          f"({len(merged)} days)")

    for older_dt, older_path, older_data in datasets[1:]:
        overlap = set(merged.keys()) & set(older_data.keys())
        if not overlap:
            print(f"    WARNING: No overlap with {os.path.basename(older_path)}, skipping")
            continue

        scale_n = []
        scale_c = []
        for d in overlap:
            if older_data[d]["your_brand"] > 0:
                scale_n.append(merged[d]["your_brand"] / older_data[d]["your_brand"])
            if older_data[d]["competitor_avg"] > 0:
                scale_c.append(merged[d]["competitor_avg"] / older_data[d]["competitor_avg"])

        if not scale_n or not scale_c:
            continue

        sn = sum(scale_n) / len(scale_n)
        sc = sum(scale_c) / len(scale_c)
        print(f"    Rebasing {os.path.basename(older_path)}: "
              f"{len(overlap)} overlap days, scale_native={sn:.4f}, scale_comp={sc:.4f}")

        added = 0
        for date_key, vals in older_data.items():
            if date_key in merged:
                continue
            yb_r = round(vals["your_brand"] * sn, 1)
            ca_r = round(vals["competitor_avg"] * sc, 1)
            pct = round(vals["your_brand"] / vals["competitor_avg"] * 100, 2) \
                if vals["competitor_avg"] else 0
            merged[date_key] = {"your_brand": yb_r, "competitor_avg": ca_r, "pct": pct}
            added += 1

        print(f"    Added {added} earlier days from {os.path.basename(older_path)}")

    return merged


def aggregate_rebased_daily_to_weekly(merged_daily):
    """
    Aggregate rebased daily data to weekly (Monday start).
    Averages Native, CompAvg, and recomputes pct from averaged values.
    Returns dict {week_start: {your_brand, competitor_avg, pct}}.
    """
    weeks = defaultdict(lambda: {"yb": [], "ca": []})

    for date_key, vals in merged_daily.items():
        ws = monday_of(date_key)
        weeks[ws]["yb"].append(vals["your_brand"])
        weeks[ws]["ca"].append(vals["competitor_avg"])

    result = {}
    for ws in sorted(weeks.keys()):
        yb_avg = round(sum(weeks[ws]["yb"]) / len(weeks[ws]["yb"]), 2)
        ca_avg = round(sum(weeks[ws]["ca"]) / len(weeks[ws]["ca"]), 2)
        pct = round(yb_avg / ca_avg * 100, 2) if ca_avg else 0
        result[ws] = {"your_brand": yb_avg, "competitor_avg": ca_avg, "pct": pct}

    return result


# ------------------------------------------------------------------ #
#  Ad Share of Voice processing
# ------------------------------------------------------------------ #

def process_ad_sov(data, view, reference_date):
    """Process ad_sov section -> list of dicts."""
    source = data["source"]
    parsed = []
    for row in source:
        ts_raw = row[0]
        your_brand = row[1] if len(row) > 1 else 0
        comp_avg = row[2] if len(row) > 2 else 0
        rank1 = row[3] if len(row) > 3 else 0
        rank2 = row[4] if len(row) > 4 else 0
        rank3 = row[5] if len(row) > 5 else 0

        if view == "monthly":
            date_key = parse_monthly_timestamp(ts_raw)
        else:
            date_key = parse_daily_timestamp(ts_raw, reference_date)

        parsed.append({
            "date": date_key,
            "your_brand": your_brand,
            "competitor_avg": comp_avg,
            "rank1": rank1,
            "rank2": rank2,
            "rank3": rank3,
        })

    return parsed


def load_all_ad_sov_daily(data_dir, reference_date):
    """
    Load all JSON files with daily ad_sov data from data_dir.
    Ad SoV values are absolute percentages (not indexed), so no rebasing needed.
    Newer data wins for overlapping dates.
    Returns merged dict {date_key: {your_brand, competitor_avg}}.
    """
    json_files = glob.glob(os.path.join(data_dir, "*.json"))
    all_entries = []

    for fpath in json_files:
        with open(fpath) as f:
            pi_data = json.load(f)

        if pi_data.get("view") != "daily":
            continue
        if "ad_sov" not in pi_data:
            continue

        extracted_at = pi_data.get("extracted_at", "2020-01-01T00:00:00")
        extracted_dt = datetime.fromisoformat(extracted_at)

        for row in pi_data["ad_sov"]["source"]:
            ts_raw = row[0]
            date_key = parse_daily_timestamp(ts_raw, extracted_dt)
            all_entries.append((extracted_dt, date_key, {
                "your_brand": row[1] if len(row) > 1 else 0,
                "competitor_avg": row[2] if len(row) > 2 else 0,
            }))
        print(f"    Loaded {os.path.basename(fpath)}: "
              f"{len(pi_data['ad_sov']['source'])} daily ad_sov points")

    if not all_entries:
        return {}

    # Sort by (date, extraction_time) — newest extraction wins for each date
    all_entries.sort(key=lambda x: (x[1], x[0]))
    merged = {}
    for _, date_key, vals in all_entries:
        merged[date_key] = vals  # last write wins (newest extraction)

    print(f"    Total: {len(merged)} unique days after merge")
    return merged


def aggregate_ad_sov_daily_to_weekly(merged_daily):
    """
    Aggregate daily Ad SoV data to weekly (Monday start).
    Returns list of dicts with week_start, your_brand (avg), competitor_avg (avg).
    """
    weeks = defaultdict(lambda: {"yb": [], "ca": []})

    for date_key, vals in merged_daily.items():
        ws = monday_of(date_key)
        weeks[ws]["yb"].append(vals["your_brand"])
        weeks[ws]["ca"].append(vals["competitor_avg"])

    result = []
    for ws in sorted(weeks.keys()):
        yb_avg = round(sum(weeks[ws]["yb"]) / len(weeks[ws]["yb"]), 3)
        ca_avg = round(sum(weeks[ws]["ca"]) / len(weeks[ws]["ca"]), 3)
        result.append({
            "week_start": ws,
            "your_brand": yb_avg,
            "competitor_avg": ca_avg,
            "rank1": 0, "rank2": 0, "rank3": 0,
        })

    return result


def build_ad_sov_sheet_rows(parsed_data):
    """
    Build data rows for ad SoV (monthly or weekly).
    Each row: [date_key, your_brand, competitor_avg, rank1, rank2, rank3, delta, notes]
    """
    rows = []
    for entry in parsed_data:
        date_key = entry.get("week_start", entry.get("date"))
        yb = entry["your_brand"]
        ca = entry["competitor_avg"]
        delta = round(yb - ca, 2) if isinstance(yb, (int, float)) and isinstance(ca, (int, float)) else 0
        rows.append([
            date_key, yb, ca,
            entry["rank1"], entry["rank2"], entry["rank3"],
            delta, "",
        ])
    return rows


# ------------------------------------------------------------------ #
#  Sheet writers
# ------------------------------------------------------------------ #

def write_brand_recall_tab(sh, tab_name, header_row1, header_row2, col_header, new_data_rows, brand_name):
    """Write brand recall data to a tab (full rewrite, no merge with existing)."""
    ws = get_or_create_worksheet(sh, tab_name, rows=500, cols=10)

    today_str = datetime.now().strftime("%Y-%m-%d")

    all_rows = [
        [header_row1],
        [header_row2.replace("YYYY-MM-DD", today_str)],
        [""],
        col_header,
    ]
    all_rows.extend(new_data_rows)

    # Pad and sanitize
    max_cols = max(len(r) for r in all_rows) if all_rows else 1
    all_rows = [r + [""] * (max_cols - len(r)) for r in all_rows]
    sanitize_rows(all_rows)

    end_col = chr(64 + min(max_cols, 26))
    if max_cols > 26:
        end_col = "A" + chr(64 + max_cols - 26)

    # Clear sheet + formatting first to prevent Sheets auto-format issues
    ws.clear()
    # Format all cells as plain number to prevent auto-% formatting
    ws.format(f"A1:{end_col}{len(all_rows)}", {"numberFormat": {"type": "NUMBER", "pattern": "0.##"}})
    # Use RAW input to prevent Sheets from auto-interpreting values
    ws.update(range_name=f"A1:{end_col}{len(all_rows)}", values=all_rows,
              value_input_option="RAW")

    print(f"  {tab_name} updated ({len(new_data_rows)} data rows).")
    return len(new_data_rows)


def write_ad_sov_tab(sh, tab_name, header_row1, header_row2, col_header, new_data_rows):
    """Write ad SoV data to a tab with upsert behaviour."""
    ws = get_or_create_worksheet(sh, tab_name, rows=500, cols=12)

    existing_data = read_existing_data(ws)
    merged = merge_data_rows(existing_data, new_data_rows)

    today_str = datetime.now().strftime("%Y-%m-%d")

    all_rows = [
        [header_row1],
        [header_row2.replace("YYYY-MM-DD", today_str)],
        [""],
        col_header,
    ]
    all_rows.extend(merged)

    max_cols = max(len(r) for r in all_rows) if all_rows else 1
    all_rows = [r + [""] * (max_cols - len(r)) for r in all_rows]
    sanitize_rows(all_rows)

    end_col = chr(64 + min(max_cols, 26))
    if max_cols > 26:
        end_col = "A" + chr(64 + max_cols - 26)
    ws.update(range_name=f"A1:{end_col}{len(all_rows)}", values=all_rows)

    print(f"  {tab_name} updated ({len(merged)} data rows).")
    return len(merged)


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Push extracted Amazon Pi data (JSON) to Google Sheets"
    )
    parser.add_argument("--category", required=True, help="Category ID (e.g., native)")
    parser.add_argument("--data-file", default=None,
                        help="Path to a single extracted JSON file (daily or monthly)")
    parser.add_argument("--data-dir", default=None,
                        help="Directory with all Pi JSON files. For monthly Brand Recall, "
                             "all monthly files are loaded and rebased automatically.")
    parser.add_argument("--dry-run", action="store_true", help="Print without updating sheet")
    args = parser.parse_args()

    if not args.data_file and not args.data_dir:
        print("ERROR: Must specify --data-file or --data-dir")
        sys.exit(1)

    # --- Load inputs ---
    category_config = load_category_config(args.category)
    brand_name = category_config.get("display_name", args.category).split("(")[0].strip()
    comp_labels = get_competitor_labels(category_config)

    # Resolve paths
    base_dir = os.path.dirname(SCRIPT_DIR)

    if args.data_dir:
        data_dir = args.data_dir if os.path.isabs(args.data_dir) \
            else os.path.join(base_dir, args.data_dir)
    else:
        data_dir = None

    if args.data_file:
        data_path = args.data_file if os.path.isabs(args.data_file) \
            else os.path.join(base_dir, args.data_file)
    else:
        data_path = None

    print(f"Amazon Pi data collector for {category_config['display_name']}")

    summary = {
        "category": args.category,
        "tabs_written": [],
    }

    sh = None  # Spreadsheet handle, opened lazily

    def get_sheet():
        nonlocal sh
        if sh is None:
            sh = open_category_sheet(args.category)
        return sh

    # ================================================================ #
    #  BRAND RECALL — rebased multi-file merge (monthly + weekly)
    # ================================================================ #
    pct_col_name = "Native search (%) vs Competitor average"

    if data_dir:
        # --- Monthly ---
        print(f"\n--- Brand Recall (Monthly) — rebased merge from {data_dir} ---")
        reference_date = datetime.now()
        datasets = load_all_brand_recall_monthly(data_dir, reference_date)

        if datasets:
            merged = rebase_brand_recall(datasets)
            data_rows = build_brand_recall_rows(merged)
            print(f"  Total: {len(data_rows)} months after rebasing+merge")

            tab_name = "Amazon Pi - Brand Recall (Monthly)"
            col_header = [
                "Month",
                f"{brand_name} (Rebased Index)",
                "Competitor Average (Rebased Index)",
                pct_col_name,
                "Notes",
            ]
            header_row1 = "Amazon Pi \u2014 Indexed Brand Recall (Monthly)"
            header_row2 = ("Source: pi.amazon.in | Category: Water Filters & Purifiers | "
                           "Rebased to newest extraction baseline | Last updated: YYYY-MM-DD")

            if not args.dry_run:
                count = write_brand_recall_tab(
                    get_sheet(), tab_name, header_row1, header_row2,
                    col_header, data_rows, brand_name,
                )
                summary["tabs_written"].append({"tab": tab_name, "rows": count})
            else:
                print(f"  [DRY RUN] Would write to tab: {tab_name}")
                for row in data_rows:
                    print(f"    {row}")
                summary["tabs_written"].append(
                    {"tab": tab_name, "rows": len(data_rows), "dry_run": True})
        else:
            print("  No monthly brand recall JSON files found.")

        # --- Weekly (from rebased daily data) ---
        print(f"\n--- Brand Recall (Weekly) — rebased daily merge from {data_dir} ---")
        daily_datasets = load_all_brand_recall_daily(data_dir, reference_date)

        if daily_datasets:
            merged_daily = rebase_brand_recall_daily(daily_datasets)
            merged_weekly = aggregate_rebased_daily_to_weekly(merged_daily)
            data_rows = build_brand_recall_rows(merged_weekly)
            print(f"  Total: {len(merged_daily)} days → {len(data_rows)} weeks")

            tab_name = "Amazon Pi - Brand Recall (Weekly)"
            col_header = [
                "Week_Start",
                f"{brand_name} (Rebased Index)",
                "Competitor Average (Rebased Index)",
                pct_col_name,
                "Notes",
            ]
            header_row1 = "Amazon Pi \u2014 Indexed Brand Recall (Weekly from Daily)"
            header_row2 = ("Source: pi.amazon.in | Daily data rebased + averaged to "
                           "week-start (Monday) | Last updated: YYYY-MM-DD")

            if not args.dry_run:
                count = write_brand_recall_tab(
                    get_sheet(), tab_name, header_row1, header_row2,
                    col_header, data_rows, brand_name,
                )
                summary["tabs_written"].append({"tab": tab_name, "rows": count})
            else:
                print(f"  [DRY RUN] Would write to tab: {tab_name}")
                for row in data_rows:
                    print(f"    {row}")
                summary["tabs_written"].append(
                    {"tab": tab_name, "rows": len(data_rows), "dry_run": True})
        else:
            print("  No daily brand recall JSON files found.")

        # --- Ad SoV Weekly (from merged daily data) ---
        print(f"\n--- Ad Share of Voice (Weekly) — merged daily from {data_dir} ---")
        merged_sov_daily = load_all_ad_sov_daily(data_dir, reference_date)

        if merged_sov_daily:
            weekly_sov = aggregate_ad_sov_daily_to_weekly(merged_sov_daily)
            sov_data_rows = build_ad_sov_sheet_rows(weekly_sov)
            print(f"  Total: {len(merged_sov_daily)} days → {len(sov_data_rows)} weeks")

            tab_name = "Amazon Pi - Ad Share of Voice (Weekly)"
            col_header = [
                "Week_Start", f"{brand_name} (Your Brand)", "Competitor Average",
                f"{comp_labels['rank_1']} (Rank 1)",
                f"{comp_labels['rank_2']} (Rank 2)",
                f"{comp_labels['rank_3']} (Rank 3)",
                "Delta", "Notes",
            ]
            header_row1 = "Amazon Pi — Advertising Share of Voice (Weekly from Daily %)"
            header_row2 = ("Source: pi.amazon.in | Daily data averaged to week-start "
                           "(Monday) | Last updated: YYYY-MM-DD")

            if not args.dry_run:
                count = write_ad_sov_tab(
                    get_sheet(), tab_name, header_row1, header_row2,
                    col_header, sov_data_rows,
                )
                summary["tabs_written"].append({"tab": tab_name, "rows": count})
            else:
                print(f"  [DRY RUN] Would write to tab: {tab_name}")
                for row in sov_data_rows:
                    print(f"    {row}")
                summary["tabs_written"].append(
                    {"tab": tab_name, "rows": len(sov_data_rows), "dry_run": True})
        else:
            print("  No daily ad_sov JSON files found.")

    # ================================================================ #
    #  SINGLE-FILE MODE (for SoV data)
    # ================================================================ #
    if data_path:
        if not os.path.exists(data_path):
            print(f"ERROR: Data file not found: {data_path}")
            sys.exit(1)

        with open(data_path) as f:
            pi_data = json.load(f)

        view = pi_data.get("view", "monthly")
        extracted_at = pi_data.get("extracted_at", datetime.now().isoformat())
        reference_date = datetime.fromisoformat(extracted_at)

        print(f"\n  Single-file mode: {data_path}")
        print(f"  View: {view} | Extracted at: {extracted_at}")

        # Note: Brand Recall is handled via --data-dir above.
        # Single-file mode is kept for Ad SoV only.
        if "brand_recall" in pi_data and view == "daily" and not data_dir:
            # Fallback: if no --data-dir, process daily brand recall from single file
            print("\n--- Brand Recall (Weekly from Daily) — single file ---")
            parsed = process_brand_recall(pi_data["brand_recall"], view, reference_date)
            weekly_data = {}
            weekly_agg = aggregate_daily_to_weekly(parsed, ["your_brand", "competitor_avg"])
            for entry in weekly_agg:
                yb = entry["your_brand"]
                ca = entry["competitor_avg"]
                pct = round(yb / ca * 100, 2) if ca else 0
                weekly_data[entry["week_start"]] = {
                    "your_brand": yb, "competitor_avg": ca, "pct": pct}
            data_rows = build_brand_recall_rows(weekly_data)

            tab_name = "Amazon Pi - Brand Recall (Weekly)"
            col_header = ["Week_Start", f"{brand_name} (Rebased Index)",
                          "Competitor Average (Rebased Index)", pct_col_name, "Notes"]
            header_row1 = "Amazon Pi \u2014 Indexed Brand Recall (Weekly from Daily)"
            header_row2 = ("Source: pi.amazon.in | Daily data averaged to week-start "
                           "(Monday) | Last updated: YYYY-MM-DD")

            if not args.dry_run:
                count = write_brand_recall_tab(
                    get_sheet(), tab_name, header_row1, header_row2,
                    col_header, data_rows, brand_name,
                )
                summary["tabs_written"].append({"tab": tab_name, "rows": count})
            else:
                print(f"  [DRY RUN] Would write to tab: {tab_name}")
                for row in data_rows:
                    print(f"    {row}")
                summary["tabs_written"].append(
                    {"tab": tab_name, "rows": len(data_rows), "dry_run": True})

        # --- Ad Share of Voice ---
        if "ad_sov" in pi_data:
            print(f"\n--- Ad Share of Voice ({view}) ---")
            parsed = process_ad_sov(pi_data["ad_sov"], view, reference_date)
            print(f"  Parsed {len(parsed)} data points.")

            rank1_label = f"{comp_labels['rank_1']} (Rank 1)"
            rank2_label = f"{comp_labels['rank_2']} (Rank 2)"
            rank3_label = f"{comp_labels['rank_3']} (Rank 3)"

            if view == "monthly":
                tab_name = "Amazon Pi - Ad Share of Voice (Monthly)"
                data_rows = build_ad_sov_sheet_rows(parsed)
                col_header = [
                    "Month", f"{brand_name} (Your Brand)", "Competitor Average",
                    rank1_label, rank2_label, rank3_label, "Delta", "Notes",
                ]
                header_row1 = "Amazon Pi \u2014 Advertising Share of Voice (Monthly %)"
                header_row2 = ("Source: pi.amazon.in | View: First Page of Search, "
                               "Sponsored Product | Last updated: YYYY-MM-DD")
            else:
                tab_name = "Amazon Pi - Ad Share of Voice (Weekly)"
                weekly = aggregate_daily_to_weekly(
                    parsed, ["your_brand", "competitor_avg", "rank1", "rank2", "rank3"]
                )
                data_rows = build_ad_sov_sheet_rows(weekly)
                col_header = [
                    "Week_Start", f"{brand_name} (Your Brand)", "Competitor Average",
                    rank1_label, rank2_label, rank3_label, "Delta", "Notes",
                ]
                header_row1 = "Amazon Pi \u2014 Advertising Share of Voice (Weekly from Daily %)"
                header_row2 = ("Source: pi.amazon.in | Daily data averaged to week-start "
                               "(Monday) | Last updated: YYYY-MM-DD")
                print(f"  Aggregated to {len(weekly)} weeks.")

            if not args.dry_run:
                count = write_ad_sov_tab(
                    get_sheet(), tab_name, header_row1, header_row2,
                    col_header, data_rows,
                )
                summary["tabs_written"].append({"tab": tab_name, "rows": count})
            else:
                print(f"  [DRY RUN] Would write to tab: {tab_name}")
                for row in data_rows[:5]:
                    print(f"    {row}")
                if len(data_rows) > 5:
                    print(f"    ... and {len(data_rows) - 5} more rows")
                summary["tabs_written"].append(
                    {"tab": tab_name, "rows": len(data_rows), "dry_run": True})

    # --- Output ---
    print(f"\n{'='*60}")
    print("=== Amazon Pi Collection Summary ===")
    for tab in summary["tabs_written"]:
        dry = " (dry run)" if tab.get("dry_run") else ""
        print(f"  {tab['tab']}: {tab['rows']} rows{dry}")

    print(f"\n__JSON_OUTPUT__:{json.dumps(summary)}")
    return summary


if __name__ == "__main__":
    main()
