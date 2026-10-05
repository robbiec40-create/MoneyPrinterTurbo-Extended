"""
A tiny on-disk history of recently generated video topics, so scheduled
runs (see scripts/scheduled_video_job.py) can tell the LLM what to avoid
repeating. This is intentionally simple - a JSON list on disk, not a
database - since it's just steering an LLM prompt, not a source of truth
anything else depends on.
"""

import json
import os
from typing import List

from loguru import logger

from app.utils import utils

_HISTORY_FILE = os.path.join(utils.storage_dir(), "topic_history.json")


def load_recent_topics(limit: int = 20) -> List[str]:
    if not os.path.exists(_HISTORY_FILE):
        return []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            topics = json.load(f)
        if not isinstance(topics, list):
            return []
        return topics[-limit:]
    except Exception as e:
        logger.warning(f"failed to load topic history: {str(e)}")
        return []


def record_topic(topic: str, keep_last: int = 100) -> None:
    topics = load_recent_topics(limit=keep_last)
    topics.append(topic)
    topics = topics[-keep_last:]
    try:
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"failed to save topic history: {str(e)}")
