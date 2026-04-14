#!/usr/bin/env python3
"""
Generate Slack-formatted report from collected data.

Usage: python3 report_generator.py --category native
"""

import argparse
import json
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sheets_client import load_category_config, open_category_sheet

DASHBOARD_URL = "https://native-brand-tracker.streamlit.app/native"


def _safe_float(val, default=0.0):
    try:
        return float(str(val).replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return default


def _delta_str(current, previous):
    """Return '+Xpp' or '-Xpp' string."""
    diff = round(current - previous, 1)
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.1f}pp"


def main():
    parser = argparse.ArgumentParser(description="Generate Slack report")
    parser.add_argument("--category", required=True, help="Category ID")
    args = parser.parse_args()

    config = load_category_config(args.category)
    display_name = config["display_name"]
    sheet_url = config.get("google_sheet_url", "")

    sh = open_category_sheet(args.category)

    report_lines = []
    report_lines.append(f"*Native Brand Tracker — Week of {datetime.now().strftime('%b %d, %Y')}*")
    report_lines.append("")

    # ── Google Trends (Weekly) ─────────────────────────────────────
    try:
        try:
            ws_trends = sh.worksheet("Raw_Weekly_Trends")
        except Exception:
            ws_trends = sh.worksheet("Trends Indexed Searches")

        trends_data = ws_trends.get_all_values()
        headers = trends_data[0] if trends_data else []

        if len(trends_data) >= 3:
            latest = trends_data[-1]
            prev = trends_data[-2]

            # Find key columns
            def _find_col(keyword):
                for i, h in enumerate(headers):
                    if keyword in h.lower():
                        return i
                return None

            native_i = _find_col("native water")
            aqua_i = _find_col("aquaguard water")
            kent_i = _find_col("kent water")

            report_lines.append("*Google: Native vs Competitors (Weekly, 4-Week Moving Avg)*")

            if native_i and aqua_i:
                n_now, a_now = _safe_float(latest[native_i]), _safe_float(latest[aqua_i])
                n_prev, a_prev = _safe_float(prev[native_i]), _safe_float(prev[aqua_i])
                pct_now = round(n_now / a_now * 100, 1) if a_now > 0 else 0
                pct_prev = round(n_prev / a_prev * 100, 1) if a_prev > 0 else 0
                report_lines.append(f"• Native as % of Aquaguard: *{pct_now:.0f}%* ({_delta_str(pct_now, pct_prev)} WoW)")

            if native_i and kent_i:
                n_now, k_now = _safe_float(latest[native_i]), _safe_float(latest[kent_i])
                n_prev, k_prev = _safe_float(prev[native_i]), _safe_float(prev[kent_i])
                pct_now = round(n_now / k_now * 100, 1) if k_now > 0 else 0
                pct_prev = round(n_prev / k_prev * 100, 1) if k_prev > 0 else 0
                report_lines.append(f"• Native as % of Kent: *{pct_now:.0f}%* ({_delta_str(pct_now, pct_prev)} WoW)")

            report_lines.append("")
    except Exception as e:
        report_lines.append(f"_Google Trends data unavailable: {e}_")
        report_lines.append("")

    # ── Monthly Search Volume (Google Ads KP) ────────────────────
    try:
        try:
            ws_vol = sh.worksheet("Raw_Monthly_KP")
        except Exception:
            ws_vol = sh.worksheet("Monthly Search Volume")

        vol_data = ws_vol.get_all_values()
        if len(vol_data) >= 2:
            vol_headers = vol_data[0]
            latest_kp = vol_data[-1]

            def _find_vol_col(keyword):
                for i, h in enumerate(vol_headers):
                    if keyword in h.lower() and "total" in h.lower():
                        return i
                return None

            native_vi = _find_vol_col("native")
            aqua_vi = _find_vol_col("aquaguard")
            kent_vi = _find_vol_col("kent")
            atom_vi = _find_vol_col("atomberg")

            month = latest_kp[0] if latest_kp else "N/A"
            parts = []
            if native_vi:
                parts.append(f"Native: *{latest_kp[native_vi]}*")
            if aqua_vi:
                parts.append(f"Aquaguard: *{latest_kp[aqua_vi]}*")
            if kent_vi:
                parts.append(f"Kent: *{latest_kp[kent_vi]}*")
            if atom_vi:
                parts.append(f"Atomberg: *{latest_kp[atom_vi]}*")

            if parts:
                report_lines.append(f"*Google: Monthly Search Volume — {month}*")
                report_lines.append(f"• {' | '.join(parts)}")
                report_lines.append("")
    except Exception as e:
        report_lines.append(f"_Volume data unavailable: {e}_")
        report_lines.append("")

    # ── Amazon Pi — Brand Recall ─────────────────────────────────
    pi_config = config.get("amazon_pi", {})
    amazon_pi_available = False

    if pi_config.get("enabled"):
        # Brand Recall (Weekly)
        try:
            ws_recall_w = sh.worksheet("Amazon Pi - Brand Recall (Weekly)")
            recall_w_data = ws_recall_w.get_all_values()
            if len(recall_w_data) > 5:
                latest = recall_w_data[-1]
                prev = recall_w_data[-2]
                native_idx = _safe_float(latest[1])
                comp_idx = _safe_float(latest[2])
                pct_now = round(native_idx / comp_idx * 100, 1) if comp_idx > 0 else 0

                native_idx_prev = _safe_float(prev[1])
                comp_idx_prev = _safe_float(prev[2])
                pct_prev = round(native_idx_prev / comp_idx_prev * 100, 1) if comp_idx_prev > 0 else 0

                report_lines.append("*Amazon: Brand Recall (Weekly)*")
                report_lines.append(f"• Native indexed searches at *{pct_now:.0f}%* of competitor average ({_delta_str(pct_now, pct_prev)} WoW)")
                report_lines.append(f"• Native Index: *{native_idx:.0f}* | Competitor Average Index: *{comp_idx:.0f}*")
                report_lines.append("")
                amazon_pi_available = True
        except Exception:
            pass

        # Ad Share of Voice (Weekly)
        try:
            ws_sov_w = sh.worksheet("Amazon Pi - Ad Share of Voice (Weekly)")
            sov_w_data = ws_sov_w.get_all_values()
            if len(sov_w_data) > 5:
                sov_headers = sov_w_data[3]  # Row 4 is header
                latest = sov_w_data[-1]
                prev = sov_w_data[-2]

                native_sov = _safe_float(latest[1])
                comp_sov = _safe_float(latest[2])
                native_sov_prev = _safe_float(prev[1])

                report_lines.append("*Amazon: Advertising Share of Voice (Weekly)*")
                report_lines.append(f"• Native: *{native_sov:.1f}%* vs Competitor Average: *{comp_sov:.1f}%* ({_delta_str(native_sov, native_sov_prev)} WoW)")

                # Monthly tab has rank breakdowns
                try:
                    ws_sov_m = sh.worksheet("Amazon Pi - Ad Share of Voice (Monthly)")
                    sov_m_data = ws_sov_m.get_all_values()
                    if len(sov_m_data) > 5:
                        sov_m_headers = sov_m_data[3]
                        latest_m = sov_m_data[-1]
                        rank_parts = []
                        for i in range(3, min(len(sov_m_headers), len(latest_m))):
                            h = sov_m_headers[i]
                            if h and h not in ("Notes", "Delta", ""):
                                rank_parts.append(f"{h}: *{latest_m[i]}%*")
                        if rank_parts:
                            report_lines.append(f"• {' | '.join(rank_parts)}")
                except Exception:
                    pass

                report_lines.append("")
                amazon_pi_available = True
        except Exception:
            pass

        if not amazon_pi_available:
            report_lines.append("_Amazon Pi: Skipped — Chrome not connected or data unavailable_")
            report_lines.append("")

    # ── Footer ────────────────────────────────────────────────────
    report_lines.append(f"<{DASHBOARD_URL}|Live Dashboard →> · <{sheet_url}|Raw Data →>")

    report = "\n".join(report_lines)
    print(report)
    print(f"\n__SLACK_REPORT__:{report}")

    return report


if __name__ == "__main__":
    main()
