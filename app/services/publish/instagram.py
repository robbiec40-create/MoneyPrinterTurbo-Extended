"""
Publish a finished video to Instagram as a Reel via the Instagram Graph API.

Unlike YouTube's resumable file upload, Instagram's API does not accept
raw video bytes - it needs a `video_url` that Instagram's own servers can
fetch the file from over HTTPS. This module builds that URL from the
app's own FastAPI server, which already serves rendered videos publicly
under /tasks/ (see app/asgi.py's StaticFiles mount), so no separate file
host is needed - just a `public_base_url` pointing at wherever that
FastAPI server is reachable from the internet (e.g. your Railway domain).

Required config (config.toml):
    [app]
    public_base_url = "https://your-app.up.railway.app"  # or any public HTTPS URL

    [instagram]
    access_token = "..."   # long-lived token, see scripts/instagram_auth.py
    ig_user_id = "..."     # Instagram Business Account ID

See docs/instagram-publishing.md for the full one-time setup.
"""

import os
import time
from typing import Optional

import requests
from loguru import logger

from app.config import config
from app.utils import utils

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Instagram Reels published via the API are capped at 90 seconds.
MAX_REEL_DURATION_SECONDS = 90

# How long to poll a media container for processing to finish before
# giving up. Instagram's own docs say this is usually seconds, but can
# take several minutes for larger files.
CONTAINER_POLL_TIMEOUT_SECONDS = 300
CONTAINER_POLL_INTERVAL_SECONDS = 5


class InstagramPublishError(Exception):
    """Raised for configuration problems that prevent even attempting a publish."""


def _build_public_video_url(video_path: str) -> str:
    """
    Map a local rendered-video path to the public URL the FastAPI server
    already serves it at (via the /tasks StaticFiles mount - see
    app/asgi.py), so Instagram's servers can fetch it.
    """
    public_base_url = config.app.get("public_base_url", "").rstrip("/")
    if not public_base_url:
        raise InstagramPublishError(
            "config.toml's [app].public_base_url is not set - Instagram's "
            "API needs a public HTTPS URL it can fetch the video from, not "
            "a local file. Set it to wherever your FastAPI server "
            "(main.py) is reachable from the internet. See "
            "docs/instagram-publishing.md."
        )

    task_root = utils.task_dir()
    try:
        rel_path = os.path.relpath(video_path, task_root)
    except ValueError:
        rel_path = None
    if not rel_path or rel_path.startswith(".."):
        raise InstagramPublishError(
            f"{video_path!r} is not under the task storage directory "
            f"({task_root!r}), so it isn't served at a public URL. "
            "Instagram can only publish videos the app itself is hosting."
        )

    # matches the "/tasks" mount name in app/asgi.py
    return f"{public_base_url}/tasks/{rel_path}"


def _create_media_container(
    video_url: str, caption: str, ig_user_id: str, access_token: str
) -> Optional[str]:
    resp = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],  # Instagram's caption length limit
            "access_token": access_token,
        },
        timeout=(30, 60),
    )
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        logger.error(f"instagram media container creation failed: {data}")
        return None
    return data["id"]


def _wait_for_container(container_id: str, access_token: str) -> bool:
    deadline = time.monotonic() + CONTAINER_POLL_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        resp = requests.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=(30, 30),
        )
        data = resp.json()
        status_code = data.get("status_code")

        if status_code == "FINISHED":
            return True
        if status_code == "ERROR":
            logger.error(f"instagram media container processing failed: {data}")
            return False

        logger.info(f"instagram media container status: {status_code}, waiting...")
        time.sleep(CONTAINER_POLL_INTERVAL_SECONDS)

    logger.error(
        f"instagram media container {container_id} did not finish processing "
        f"within {CONTAINER_POLL_TIMEOUT_SECONDS}s"
    )
    return False


def _publish_container(
    container_id: str, ig_user_id: str, access_token: str
) -> Optional[str]:
    resp = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
        timeout=(30, 60),
    )
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        logger.error(f"instagram media publish failed: {data}")
        return None
    return data["id"]


def upload_reel(
    video_path: str,
    caption: str = "",
    ig_user_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Optional[str]:
    """
    Publish a local video file to Instagram as a Reel.

    Args:
        video_path: local path to the rendered video file
        caption: Instagram caption (capped at 2200 chars)
        ig_user_id: which Instagram Business Account to publish to (see
            docs/multi-client-publishing.md). Omit to use the single
            global [instagram].ig_user_id.
        access_token: that account's access token. Omit to use the
            single global [instagram].access_token.

    Returns the published media's Instagram ID on success, or None on
    failure (logged, never raised past this point so a failed publish
    doesn't fail the render task).
    """
    if not os.path.exists(video_path):
        logger.error(f"instagram publish failed: file not found: {video_path}")
        return None

    ig_user_id = ig_user_id or config.instagram.get("ig_user_id", "")
    access_token = access_token or config.instagram.get("access_token", "")
    if not ig_user_id or not access_token:
        logger.error(
            "instagram publish failed: ig_user_id/access_token not set "
            "(neither passed explicitly nor in [instagram] config) - "
            "see docs/instagram-publishing.md"
        )
        return None

    try:
        video_url = _build_public_video_url(video_path)
    except InstagramPublishError as e:
        logger.error(f"instagram publish failed: {str(e)}")
        return None

    logger.info(f"start instagram publish: {video_path} -> {video_url}")

    try:
        container_id = _create_media_container(
            video_url, caption, ig_user_id, access_token
        )
        if not container_id:
            return None

        if not _wait_for_container(container_id, access_token):
            return None

        media_id = _publish_container(container_id, ig_user_id, access_token)
        if media_id:
            logger.success(f"instagram publish succeeded: media id {media_id}")
        return media_id
    except requests.exceptions.RequestException as e:
        logger.error(f"instagram publish failed: request error: {str(e)}")
    except Exception as e:
        logger.error(f"instagram publish failed: {str(e)}")

    return None
