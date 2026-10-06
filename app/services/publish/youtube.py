"""
Upload a finished video to YouTube as a Short/public video via the YouTube
Data API v3.

This talks to Google's API with a long-lived OAuth refresh token rather
than doing an interactive login at upload time, because this app usually
runs on a headless server. The token is generated once, out-of-band, by
running scripts/youtube_auth.py on a machine with a browser - see
docs/youtube-publishing.md for the full setup walkthrough.

Required config (config.toml, [youtube] section):
    client_secrets_file = "path/to/client_secret.json"  # from Google Cloud Console
    token_file = "path/to/token.json"                    # produced by scripts/youtube_auth.py
"""

import os
from typing import Optional

from loguru import logger

from app.config import config

# A video uploaded with only this scope cannot be made public automatically
# by apps that haven't passed Google's verification/audit; see
# docs/youtube-publishing.md for what this means for an unverified app.
YOUTUBE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


class YouTubeAuthError(Exception):
    """Raised when the stored OAuth token is missing or invalid."""


def _load_credentials(token_file: Optional[str] = None):
    """
    Load the OAuth credentials saved by scripts/youtube_auth.py, refreshing
    the access token if it has expired. Never starts an interactive login
    flow - this is meant to run unattended on a server.

    Args:
        token_file: path to a specific client's token.json. If omitted,
            falls back to the single global [youtube].token_file - this
            is what keeps the WebUI/single-owner flow (task.py calling
            upload_video with no token_file) working unchanged under
            multi-client use (see docs/multi-client-publishing.md).
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_file = token_file or config.youtube.get("token_file", "")
    if not token_file or not os.path.exists(token_file):
        raise YouTubeAuthError(
            f"YouTube token file not found: {token_file!r}. Run "
            "scripts/youtube_auth.py on a machine with a browser first - "
            "see docs/youtube-publishing.md."
        )

    creds = Credentials.from_authorized_user_file(token_file, YOUTUBE_UPLOAD_SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist the refreshed access token so we don't refresh every call.
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    if not creds.valid:
        raise YouTubeAuthError(
            "YouTube credentials are invalid and could not be refreshed. "
            "Re-run scripts/youtube_auth.py to re-authenticate."
        )

    return creds


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    category_id: str = "22",  # "People & Blogs"; see docs/youtube-publishing.md
    privacy_status: str = "public",
    made_for_kids: bool = False,
    token_file: Optional[str] = None,
) -> Optional[str]:
    """
    Upload a video file to a YouTube channel.

    Args:
        video_path: local path to the rendered video file
        title: video title (YouTube caps this at 100 characters)
        description: video description (caps at 5000 characters)
        tags: list of keyword tags
        category_id: YouTube video category ID, default "22" (People & Blogs)
        privacy_status: "public", "unlisted", or "private"
        made_for_kids: must be set accurately - this is a legal requirement
            under COPPA, not a style choice. Default False.
        token_file: which channel to upload to - a specific client's
            token.json (see docs/multi-client-publishing.md). Omit to
            use the single global [youtube].token_file.

    Returns:
        The uploaded video's YouTube ID on success, or None on failure.
    """
    if not os.path.exists(video_path):
        logger.error(f"youtube upload failed: file not found: {video_path}")
        return None

    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.error(
            "youtube upload failed: google-api-python-client is not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib "
            "google-auth-httplib2"
        )
        return None

    try:
        creds = _load_credentials(token_file)
    except YouTubeAuthError as e:
        logger.error(f"youtube upload failed: {str(e)}")
        return None

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    try:
        youtube = build(API_SERVICE_NAME, API_VERSION, credentials=creds)
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        logger.info(f"start youtube upload: {video_path} -> title={title!r}")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"youtube upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        logger.success(
            f"youtube upload succeeded: https://youtube.com/watch?v={video_id}"
        )
        return video_id
    except HttpError as e:
        logger.error(f"youtube upload failed: HTTP {e.resp.status}: {e.content}")
    except Exception as e:
        logger.error(f"youtube upload failed: {str(e)}")

    return None
