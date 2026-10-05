#!/usr/bin/env python3
"""
Fully unattended video job: picks its own topic, generates the video,
and publishes it - no human input at all.

Meant to be invoked on a schedule by something outside this process
(Railway Cron Job, OS cron, a GitHub Actions scheduled workflow, etc.) -
see docs/scheduled-publishing.md for how to wire that up. This script
itself is one-shot: run it, it does one video, it exits.

Two modes:

- --client CLIENT_ID (multi-client mode - see
  docs/multi-client-publishing.md): looks up that client's theme and
  publishing credentials from config.toml's `[[clients]]` entries, and
  publishes using THAT CLIENT's own YouTube/Instagram accounts, not the
  global [youtube]/[instagram] config. This is the mode to use once you
  have real clients, each with their own accounts.

- --theme "some theme" (or no flag at all, single-owner mode): the
  original behavior - uses config.toml's [scheduler] defaults and the
  global [youtube]/[instagram] config (i.e. your own accounts). Useful
  for testing, or if you're just running this for yourself rather than
  clients.

These are mutually exclusive - pass one or the other, not both.

Each client (or, in single-owner mode, each theme) gets its own
topic-history bucket (storage/topic_history_<client-id-or-theme>.json)
so they don't steer each other's topic selection.

Exit code 0 on a successful render (publish failures are logged but
don't affect the exit code - a video that rendered but didn't publish
is still a completed job, not a failure), non-zero if the render itself
failed.
"""

import argparse
import sys

from loguru import logger

from app.config import config
from app.models.schema import VideoParams
from app.services import clients, llm, task, topic_history
from app.services.publish import instagram as instagram_publish
from app.services.publish import youtube as youtube_publish
from app.utils import utils


def _publish_for_client(client, final_video_paths, title, description, caption):
    """
    Publish each rendered video using a specific client's own credentials
    - never the global [youtube]/[instagram] config. A client with a
    platform's credentials left unset simply skips that platform.
    """
    youtube_video_ids = []
    instagram_media_ids = []

    token_file = client.get("youtube_token_file", "")
    ig_user_id = client.get("instagram_ig_user_id", "")
    ig_access_token = client.get("instagram_access_token", "")

    for video_path in final_video_paths:
        if token_file:
            youtube_video_ids.append(
                youtube_publish.upload_video(
                    video_path=video_path,
                    title=title,
                    description=description,
                    privacy_status=client.get("youtube_privacy_status", "public"),
                    token_file=token_file,
                )
            )
        else:
            youtube_video_ids.append(None)

        if ig_user_id and ig_access_token:
            instagram_media_ids.append(
                instagram_publish.upload_reel(
                    video_path,
                    caption=caption,
                    ig_user_id=ig_user_id,
                    access_token=ig_access_token,
                )
            )
        else:
            instagram_media_ids.append(None)

    return youtube_video_ids, instagram_media_ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client",
        default=None,
        help="Run for this client ID (from config.toml's [[clients]]) - "
        "publishes to that client's own YouTube/Instagram accounts. "
        "Mutually exclusive with --theme.",
    )
    parser.add_argument(
        "--theme",
        default=None,
        help="Single-owner mode: overrides [scheduler].theme for this "
        "run, publishing via the global [youtube]/[instagram] config. "
        "Mutually exclusive with --client.",
    )
    args = parser.parse_args()

    if args.client and args.theme:
        logger.error("scheduled job aborted: pass --client or --theme, not both")
        return 1

    sched = config.scheduler
    client = None

    if args.client:
        client = clients.get_client(args.client)
        if not client:
            logger.error(
                f"scheduled job aborted: no client {args.client!r} found in "
                "config.toml's [[clients]] - see docs/multi-client-publishing.md"
            )
            return 1
        theme = client.get("theme", "")
        if not theme:
            logger.error(
                f"scheduled job aborted: client {args.client!r} has no theme set"
            )
            return 1
        history_key = args.client
    else:
        theme = args.theme or sched.get("theme", "political satire")
        history_key = theme

    def client_or_sched(key, default=None):
        if client and client.get(key) is not None:
            return client[key]
        return sched.get(key, default)

    history_size = sched.get("topic_history_size", 20)
    recent_topics = topic_history.load_recent_topics(history_key, limit=history_size)
    topic = llm.generate_topic_idea(theme, avoid_topics=recent_topics)
    if topic.startswith("Error: "):
        logger.error(f"scheduled job aborted: could not generate a topic: {topic}")
        return 1

    # Record immediately, not just on success - an attempted-but-failed
    # topic still shouldn't be retried next run.
    topic_history.record_topic(history_key, topic)

    params = VideoParams(
        video_subject=topic,
        video_source=client_or_sched("video_source", "pexels"),
        voice_name=client_or_sched("voice_name", "en-US-AriaNeural-Female"),
        video_aspect=client_or_sched("video_aspect", "9:16"),  # VideoAspect.portrait
        paragraph_number=client_or_sched("paragraph_number", 1),
        output_resolution_short_side=client_or_sched("output_resolution_short_side"),
        # Multi-client mode always publishes itself, below, with the
        # client's own credentials - task.start() must never try to
        # publish with the global config on a client's behalf.
        youtube_auto_publish=False if client else sched.get("youtube_auto_publish", False),
        youtube_privacy_status=sched.get("youtube_privacy_status", "public"),
        instagram_auto_publish=False if client else sched.get("instagram_auto_publish", False),
    )

    task_id = utils.get_uuid()
    logger.info(
        f"scheduled job starting: task_id={task_id}, "
        f"client={args.client!r}, theme={theme!r}, topic={topic!r}"
    )

    result = task.start(task_id, params, stop_at="video")

    if not result or not result.get("videos"):
        logger.error(f"scheduled job failed: task {task_id} produced no videos")
        return 1

    youtube_video_ids = result.get("youtube_video_ids")
    instagram_media_ids = result.get("instagram_media_ids")

    if client:
        youtube_video_ids, instagram_media_ids = _publish_for_client(
            client,
            result["videos"],
            title=topic,
            description=result.get("script", topic),
            caption=topic,
        )

    logger.success(
        f"scheduled job finished: task_id={task_id}, "
        f"videos={result.get('videos')}, "
        f"youtube_video_ids={youtube_video_ids}, "
        f"instagram_media_ids={instagram_media_ids}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
