#!/usr/bin/env python3
"""
Fully unattended video job: picks its own topic, generates the video,
and publishes it - no human input at all.

Meant to be invoked on a schedule by something outside this process
(Railway Cron Job, OS cron, a GitHub Actions scheduled workflow, etc.) -
see docs/scheduled-publishing.md for how to wire that up. This script
itself is one-shot: run it, it does one video, it exits.

All the "what to generate" defaults come from config.toml's [scheduler]
section - nothing is passed on the command line, since nothing outside
this process is expected to know or care about video-generation details.

Exit code 0 on a successful render (publish failures are logged but
don't affect the exit code - see app/services/task.py's
publish_videos_to_youtube/_instagram, which deliberately don't fail the
task over a publish error), non-zero if the render itself failed.
"""

import sys

from loguru import logger

from app.config import config
from app.models.schema import VideoParams
from app.services import llm, task, topic_history
from app.utils import utils


def main() -> int:
    sched = config.scheduler

    theme = sched.get("theme", "political satire")
    history_size = sched.get("topic_history_size", 20)

    recent_topics = topic_history.load_recent_topics(limit=history_size)
    topic = llm.generate_topic_idea(theme, avoid_topics=recent_topics)
    if topic.startswith("Error: "):
        logger.error(f"scheduled job aborted: could not generate a topic: {topic}")
        return 1

    # Record immediately, not just on success - an attempted-but-failed
    # topic still shouldn't be retried next run.
    topic_history.record_topic(topic)

    params = VideoParams(
        video_subject=topic,
        video_source=sched.get("video_source", "pexels"),
        voice_name=sched.get("voice_name", ""),
        video_aspect=sched.get("video_aspect", "9:16"),  # VideoAspect.portrait
        paragraph_number=sched.get("paragraph_number", 1),
        youtube_auto_publish=sched.get("youtube_auto_publish", False),
        youtube_privacy_status=sched.get("youtube_privacy_status", "public"),
        instagram_auto_publish=sched.get("instagram_auto_publish", False),
    )

    task_id = utils.get_uuid()
    logger.info(f"scheduled job starting: task_id={task_id}, topic={topic!r}")

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
