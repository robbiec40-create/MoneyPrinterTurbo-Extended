#!/usr/bin/env python3
"""
One-time YouTube OAuth setup.

Run this ONCE, on a machine with a web browser (your laptop, not a
headless server), to produce a token.json that the server-side uploader
(app/services/publish/youtube.py) reuses indefinitely without logging in
again.

Prerequisites (see docs/youtube-publishing.md for the full walkthrough):
  1. A Google Cloud project with the "YouTube Data API v3" enabled.
  2. An OAuth 2.0 Client ID of type "Desktop app", downloaded as
     client_secret.json.
  3. pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

Usage:
    python scripts/youtube_auth.py --client-secrets client_secret.json --token-out token.json

This opens a browser window for you to log in and grant upload access to
your YouTube channel, then writes the resulting refresh token to
--token-out. Upload that file to wherever your server reads
config.toml's [youtube].token_file from (keep it secret - it grants
upload access to your channel).
"""

import argparse
import sys


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-secrets",
        default="client_secret.json",
        help="Path to the OAuth client secrets file downloaded from Google Cloud Console",
    )
    parser.add_argument(
        "--token-out",
        default="token.json",
        help="Where to write the resulting token (point config.toml's [youtube].token_file here)",
    )
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Missing dependency. Run:\n"
            "  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2",
            file=sys.stderr,
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    # Spins up a local loopback server and opens your browser to Google's
    # consent screen - this is why this script needs to run somewhere with
    # a browser, not on the headless server.
    creds = flow.run_local_server(port=0)

    with open(args.token_out, "w") as f:
        f.write(creds.to_json())

    print(f"Saved credentials to {args.token_out}")
    print(
        "Copy this file to your server and point config.toml's "
        "[youtube].token_file at it. Keep it secret - do not commit it."
    )


if __name__ == "__main__":
    main()
