#!/usr/bin/env python3
"""
One-time Instagram long-lived token exchange + IG Business Account ID lookup.

Unlike YouTube's OAuth flow, Meta doesn't give installed apps a permanent
refresh token - what you get here is a long-lived access token that lasts
about 60 days and needs to be re-exchanged periodically (this same script,
re-run with a fresh short-lived token). See docs/instagram-publishing.md
for the full walkthrough, including how to get the short-lived token in
the first place (Graph API Explorer).

Usage:
    python scripts/instagram_auth.py \
      --app-id YOUR_APP_ID \
      --app-secret YOUR_APP_SECRET \
      --short-lived-token TOKEN_FROM_GRAPH_API_EXPLORER

Prints the long-lived access token and, if it can find one, your
Instagram Business Account ID - put both into config.toml's
[instagram] section.
"""

import argparse
import sys

import requests

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def exchange_for_long_lived_token(app_id: str, app_secret: str, short_lived_token: str) -> str:
    resp = requests.get(
        f"{GRAPH_API_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        print(f"Token exchange failed: {data}", file=sys.stderr)
        sys.exit(1)
    return data["access_token"]


def find_instagram_business_account_id(long_lived_token: str) -> str | None:
    """
    Walk Pages you manage -> each Page's linked Instagram Business Account.
    Returns the first one found, or None if your account isn't set up as
    a Business account linked to a Facebook Page yet.
    """
    resp = requests.get(
        f"{GRAPH_API_BASE}/me/accounts",
        params={"access_token": long_lived_token},
        timeout=30,
    )
    pages = resp.json().get("data", [])
    for page in pages:
        page_id = page.get("id")
        page_resp = requests.get(
            f"{GRAPH_API_BASE}/{page_id}",
            params={
                "fields": "instagram_business_account",
                "access_token": long_lived_token,
            },
            timeout=30,
        )
        ig_account = page_resp.json().get("instagram_business_account")
        if ig_account:
            return ig_account.get("id")
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-secret", required=True)
    parser.add_argument("--short-lived-token", required=True)
    args = parser.parse_args()

    long_lived_token = exchange_for_long_lived_token(
        args.app_id, args.app_secret, args.short_lived_token
    )
    print(f"\nLong-lived access token (lasts ~60 days):\n{long_lived_token}\n")

    ig_user_id = find_instagram_business_account_id(long_lived_token)
    if ig_user_id:
        print(f"Instagram Business Account ID:\n{ig_user_id}\n")
    else:
        print(
            "Could not find a linked Instagram Business Account. Make sure "
            "your Instagram account is set to Business (or Creator, then "
            "switched to Business) and linked to a Facebook Page you manage. "
            "See docs/instagram-publishing.md.",
            file=sys.stderr,
        )

    print(
        "Put both values into config.toml's [instagram] section "
        "(access_token, ig_user_id). Re-run this script every ~60 days "
        "with a fresh short-lived token to keep access_token current."
    )


if __name__ == "__main__":
    main()
