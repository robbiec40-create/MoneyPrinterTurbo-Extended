# Running fully unattended (scheduled video generation)

If you never want to open the WebUI or call the API by hand, this is the
piece that closes the loop: `scripts/scheduled_video_job.py` picks its
own topic, generates a video, and publishes it to YouTube/Instagram - no
human input.

**This script itself does not schedule anything.** It's one-shot: run
it, it does one video, it exits. Something outside the script has to
call it on a timer. Three ways to do that, pick one:

## Option A: Railway Cron Job (recommended if you're already on Railway)

Railway supports a service type that runs on a schedule instead of
staying up as a web server:

1. In your Railway project, add a new service from the same repo/Dockerfile.
2. Settings → set a **Cron Schedule**, e.g. `0 18 * * 1,3,5` (6pm UTC on
   Mon/Wed/Fri - adjust to your timezone and the days you want).
3. Settings → **Start Command**: `python scripts/scheduled_video_job.py`
4. Make sure this service has the same `config.toml` / environment as
   your main deployment (same volume, or same env vars) - it needs the
   same API keys and `[youtube]`/`[instagram]` credentials.

## Option B: Plain OS cron (self-hosted server)

```
# crontab -e
0 18 * * 1,3,5 cd /path/to/MoneyPrinterTurbo-Extended && python3 scripts/scheduled_video_job.py >> logs/scheduled.log 2>&1
```

## Option C: GitHub Actions scheduled workflow

Only practical if your server's config/credentials can be made available
to a GitHub Actions runner (e.g. via secrets) and the runner can reach
whatever `public_base_url` Instagram needs - usually more friction than
A or B, but an option if you want the schedule managed outside your
server entirely.

## Configuring what each run actually does

Everything the script needs is in `config.toml`'s `[scheduler]` section:

```toml
[scheduler]
theme = "political satire"       # broad theme; the LLM picks a specific topic within it each run
video_source = "pexels"
voice_name = ""                   # "" = default
video_aspect = "9:16"  # portrait
paragraph_number = 1
youtube_auto_publish = true
youtube_privacy_status = "public"
instagram_auto_publish = true
topic_history_size = 20           # how many recent topics to tell the LLM not to repeat
```

This requires `[youtube]` and/or `[instagram]` to already be configured
(see `docs/youtube-publishing.md` / `docs/instagram-publishing.md`) -
the scheduler doesn't set those up, it just uses them.

## How topic selection avoids repeats

Each run calls the LLM once to invent a specific topic within your
`theme`, telling it the last `topic_history_size` topics to avoid
repeating (stored in `storage/topic_history.json`, managed automatically
- `app/services/topic_history.py`). This is a simple steering mechanism,
not a guarantee of novelty - the LLM can still occasionally produce
something similar to an older topic further back than the history
window.

## Failure behavior

- If topic generation or the video render itself fails, the script exits
  non-zero and logs why - your cron/Railway job's own failure
  notifications (if any) will catch this.
- If the video renders successfully but a *publish* (YouTube/Instagram)
  fails, the script still exits **0** - the video was produced
  successfully, publishing is a separate concern. Check the logs for the
  specific publish error.
