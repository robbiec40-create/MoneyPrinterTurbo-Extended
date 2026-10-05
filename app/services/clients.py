"""
The multi-client registry: each client gets exactly one theme and posts
to their own YouTube/Instagram accounts, configured as a `[[clients]]`
array-of-tables in config.toml. See docs/multi-client-publishing.md for
the full onboarding process (each client runs their own OAuth setup).

This is intentionally just a thin accessor over config.clients (a list
of dicts, since TOML's array-of-tables parses that way) - no database,
no ORM, matching the rest of this app's config.toml-is-the-source-of-
truth approach.
"""

from typing import List, Optional, TypedDict

from app.config import config


class ClientConfig(TypedDict, total=False):
    id: str
    theme: str
    # Publishing credentials - all optional; a client with neither set
    # just doesn't get that platform's auto-publish.
    youtube_token_file: str
    youtube_privacy_status: str
    instagram_access_token: str
    instagram_ig_user_id: str
    # Per-client overrides of [scheduler] defaults - any omitted key
    # falls back to [scheduler]'s value.
    video_source: str
    voice_name: str
    video_aspect: str
    paragraph_number: int
    output_resolution_short_side: int


def list_clients() -> List[ClientConfig]:
    return config.clients


def get_client(client_id: str) -> Optional[ClientConfig]:
    for client in config.clients:
        if client.get("id") == client_id:
            return client
    return None
