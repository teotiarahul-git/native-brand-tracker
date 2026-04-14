#!/usr/bin/env python3
"""
Authenticate with Google APIs (Sheets, GSC, Drive).
Shared across all category trackers.

Usage: python3 auth_oauth.py
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".config")
CREDS_FILE = os.path.join(CONFIG_DIR, "credentials.json")
TOKEN_FILE = os.path.join(CONFIG_DIR, "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/drive",
]


def authenticate():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_FILE):
                print(f"ERROR: No credentials file found at {CREDS_FILE}")
                return None

            print("Opening browser for Google authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")

    print("Authentication successful.")
    return creds


def get_credentials():
    """Get valid credentials, refreshing if needed."""
    if not os.path.exists(TOKEN_FILE):
        return authenticate()

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            return authenticate()
    return creds


if __name__ == "__main__":
    authenticate()
