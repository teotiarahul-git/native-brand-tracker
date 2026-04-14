#!/usr/bin/env python3
"""
Google Sheets read/write helpers shared across all category trackers.
"""

import os
import json
import gspread
from google.oauth2.credentials import Credentials

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".config")
CATEGORIES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "categories")


def get_sheets_client():
    """Get authenticated gspread client."""
    token_file = os.path.join(CONFIG_DIR, "token.json")
    if not os.path.exists(token_file):
        raise FileNotFoundError(f"No token.json found at {token_file}. Run auth_oauth.py first.")
    creds = Credentials.from_authorized_user_file(token_file)
    return gspread.authorize(creds)


def load_category_config(category_id):
    """Load category configuration by ID."""
    config_path = os.path.join(CATEGORIES_DIR, f"{category_id}.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Category config not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def save_category_config(category_id, config):
    """Save updated category configuration."""
    config_path = os.path.join(CATEGORIES_DIR, f"{category_id}.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def open_category_sheet(category_id):
    """Open the Google Sheet for a category."""
    config = load_category_config(category_id)
    sheet_id = config.get("google_sheet_id", "")
    if not sheet_id:
        raise ValueError(f"google_sheet_id not set for category '{category_id}'")
    gc = get_sheets_client()
    return gc.open_by_key(sheet_id)


def get_or_create_worksheet(spreadsheet, title, rows=500, cols=15):
    """Get existing worksheet or create new one."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title, rows=rows, cols=cols)


def batch_update_worksheet(ws, rows, start_cell="A1"):
    """Write rows to worksheet in a single batch call."""
    if not rows:
        return
    max_cols = max(len(r) for r in rows)
    # Pad all rows to same width
    padded = [r + [""] * (max_cols - len(r)) for r in rows]
    # Calculate end cell
    end_col = chr(64 + min(max_cols, 26))  # A-Z
    if max_cols > 26:
        end_col = "A" + chr(64 + max_cols - 26)
    end_row = int(start_cell[1:]) + len(padded) - 1 if start_cell[1:].isdigit() else len(padded)
    col_letter = start_cell[0] if start_cell[0].isalpha() else "A"
    ws.update(range_name=f"{col_letter}1:{end_col}{end_row}", values=padded)


def load_keywords(category_id):
    """Load keywords for a category."""
    config = load_category_config(category_id)
    keywords_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", config["keywords_file"])
    with open(keywords_path) as f:
        return json.load(f)


def load_geo_codes():
    """Load the shared geo codes reference."""
    geo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo_codes.json")
    with open(geo_path) as f:
        return json.load(f)
