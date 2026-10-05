"""
A tiny on-disk history of recently generated video topics, so scheduled
runs (see scripts/scheduled_video_job.py) can tell the LLM what to avoid
repeating. This is intentionally simple - a JSON list on disk, not a
database - since it's just steering an LLM prompt, not a source of truth
anything else depends on.

History is kept per theme (storage/topic_history_<theme-slug>.json), so
running several themes (e.g. political satire / educational / bedtime
stories) on separate schedules doesn't have one theme's topics steer
another's away from perfectly good ideas.
"""

import json
import os
import re
from typing import List

from loguru import logger

from app.utils import utils


def _history_file(theme: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", theme.lower()).strip("_") or "default"
    return os.path.join(utils.storage_dir(), f"topic_history_{slug}.json")


def load_recent_topics(theme: str, limit: int = 20) -> List[str]:
    history_file = _history_file(theme)
    if not os.path.exists(history_file):
        return []
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            topics = json.load(f)
        if not isinstance(topics, list):
            return []
        return topics[-limit:]
    except Exception as e:
        logger.warning(f"failed to load topic history for {theme!r}: {str(e)}")
        return []


def record_topic(theme: str, topic: str, keep_last: int = 100) -> None:
    history_file = _history_file(theme)
    topics = load_recent_topics(theme, limit=keep_last)
    topics.append(topic)
    topics = topics[-keep_last:]
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"failed to save topic history for {theme!r}: {str(e)}")
