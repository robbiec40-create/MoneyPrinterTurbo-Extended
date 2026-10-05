#!/usr/bin/env python3
"""
Fully unattended video job: picks its own topic, generates the video,
and publishes it - no human input at all.

Meant to be invoked on a schedule by something outside this process
(Railway Cron Job, OS cron, a GitHub Actions scheduled workflow, etc.) -
see docs/scheduled-publishing.md for how to wire that up. This script
itself is one-shot: run it, it does one video, it exits.

Most "what to generate" defaults come from config.toml's [scheduler]
section. The one thing worth passing on the command line is --theme:
running several themes (e.g. political satire / educational / bedtime
stories), each on its own schedule, means several cron/Railway Cron
entries all invoking this same script with a different --theme, rather
than needing a separate script or config block per theme. Each theme
gets its own topic-history bucket (storage/topic_history_<theme>.json)
so they don't steer each other's topic selection.

Exit code 0 on a successful render (publish failures are logged but
don't affect the exit code - see app/services/task.py's
publish_videos_to_youtube/_instagram, which deliberately don't fail the
task over a publish error), non-zero if the render itself failed.
"""

import argparse
import sys

from loguru import logger

from app.config import config
from app.models.schema import VideoParams
from app.services import llm, task, topic_history
from app.utils import utils


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--theme",
        default=None,
        help="Overrides config.toml's [scheduler].theme for this run "
        "(use this to run several themes on separate schedules).",
    )
    args = parser.parse_args()

    sched = config.scheduler

    theme = args.theme or sched.get("theme", "political satire")
    history_size = sched.get("topic_history_size", 20)

    recent_topics = topic_history.load_recent_topics(theme, limit=history_size)
    topic = llm.generate_topic_idea(theme, avoid_topics=recent_topics)
    if topic.startswith("Error: "):
        logger.error(f"scheduled job aborted: could not generate a topic: {topic}")
        return 1

    # Record immediately, not just on success - an attempted-but-failed
    # topic still shouldn't be retried next run.
    topic_history.record_topic(theme, topic)

    params = VideoParams(
        video_subject=topic,
        video_source=sched.get("video_source", "pexels"),
        voice_name=sched.get("voice_name", "en-US-AriaNeural-Female"),
        video_aspect=sched.get("video_aspect", "9:16"),  # VideoAspect.portrait
        paragraph_number=sched.get("paragraph_number", 1),
        output_resolution_short_side=sched.get("output_resolution_short_side"),
        youtube_auto_publish=sched.get("youtube_auto_publish", False),
        youtube_privacy_status=sched.get("youtube_privacy_status", "public"),
        instagram_auto_publish=sched.get("instagram_auto_publish", False),
    )

    task_id = utils.get_uuid()
    logger.info(
        f"scheduled job starting: task_id={task_id}, theme={theme!r}, topic={topic!r}"
    )

    result = task.start(task_id, params, stop_at="video")

    if not result or not result.get("videos"):
        logger.error(f"scheduled job failed: task {task_id} produced no videos")
        return 1

    logger.success(
        f"scheduled job finished: task_id={task_id}, "
        f"videos={result.get('videos')}, "
        f"youtube_video_ids={result.get('youtube_video_ids')}, "
        f"instagram_media_ids={result.get('instagram_media_ids')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
