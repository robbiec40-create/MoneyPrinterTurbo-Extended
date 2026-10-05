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
staying up as a web server. **Railway Cron is UTC-only — there's no
timezone setting** — so an 8am US Eastern schedule has to be converted
by hand, and re-converted twice a year for daylight saving:

| | UTC offset | Cron hour for 8am ET |
|---|---|---|
| EDT (mid-Mar–early Nov, includes now) | UTC-4 | `12` |
| EST (early Nov–mid-Mar) | UTC-5 | `13` |

So right now (EDT), 8am ET is `12:00 UTC`. **You'll need to flip the
cron hour from 12 to 13 when DST ends (~first Sunday of November) and
back to 12 when it resumes (~second Sunday of March)** — Railway won't
do this for you. If that manual flip is a dealbreaker, running this on
a self-hosted server (Option B) with the system timezone set to
`America/New_York` avoids it entirely, since OS cron can be told the
timezone directly.

### Running 3 themes, each 3x/week, at 8am ET

This repo's `--theme` flag (see below) lets one script serve several
independently-scheduled themes without separate code. Add **one Railway
service per theme**, all from the same repo/Dockerfile, each with its
own Cron Schedule and Start Command. Minutes are offset slightly
(`:00`, `:05`, `:10`) so the three don't all hit Railway's scheduler in
the same instant - also a general good practice, since very popular
top-of-the-hour times (`:00` UTC) can occasionally get skipped under
Railway's own cron load:

| Service | Cron Schedule (EDT, i.e. now) | Start Command |
|---|---|---|
| satire | `0 12 * * 1,3,5` | `python scripts/scheduled_video_job.py --theme "political satire"` |
| educational | `5 12 * * 1,3,5` | `python scripts/scheduled_video_job.py --theme "educational"` |
| bedtime | `10 12 * * 1,3,5` | `python scripts/scheduled_video_job.py --theme "bedtime stories"` |

(Mon/Wed/Fri shown to match the original 3x/week-per-theme cadence
discussed when this was built — swap the `1,3,5` for whichever days you
actually want; nothing here assumes those specific days.)

For each service: Settings → **Cron Schedule** (table above, remembering
the EDT/EST flip) → **Start Command** (table above). Make sure every
service has the same `config.toml`/environment as your main deployment
(same volume or same env vars) - each needs the `[youtube]`/`[instagram]`
credentials and `public_base_url`.

## Option B: Plain OS cron (self-hosted server)

Unlike Railway, OS cron can be told a timezone directly (via `CRON_TZ`
on systems that support it, e.g. most Linux cron), so this avoids the
manual DST flip Option A needs:

```
# crontab -e
CRON_TZ=America/New_York
0 8 * * 1,3,5 cd /path/to/MoneyPrinterTurbo-Extended && python3 scripts/scheduled_video_job.py --theme "political satire" >> logs/scheduled-satire.log 2>&1
5 8 * * 1,3,5 cd /path/to/MoneyPrinterTurbo-Extended && python3 scripts/scheduled_video_job.py --theme "educational" >> logs/scheduled-educational.log 2>&1
10 8 * * 1,3,5 cd /path/to/MoneyPrinterTurbo-Extended && python3 scripts/scheduled_video_job.py --theme "bedtime stories" >> logs/scheduled-bedtime.log 2>&1
```

(`CRON_TZ` support varies by cron implementation - if yours doesn't
support it, set the system timezone instead, or convert to UTC as in
Option A.)

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
theme = "political satire"       # fallback theme if no --theme CLI arg is given
video_source = "pexels"
voice_name = ""                   # "" = default
video_aspect = "9:16"  # portrait
paragraph_number = 1
output_resolution_short_side = 750  # export at 750px short side instead of native 1080p+; None/0 = native
youtube_auto_publish = true
youtube_privacy_status = "public"
instagram_auto_publish = true
topic_history_size = 20           # how many recent topics to tell the LLM not to repeat
```

This requires `[youtube]` and/or `[instagram]` to already be configured
(see `docs/youtube-publishing.md` / `docs/instagram-publishing.md`) -
the scheduler doesn't set those up, it just uses them.

## Running multiple themes

Pass `--theme "some theme"` on the command line to override
`[scheduler].theme` for that run — this is how 3 separately-scheduled
themes (political satire / educational / bedtime stories) share one
script instead of needing 3 copies of it. Every other setting
(`video_source`, `output_resolution_short_side`, publish flags, etc.)
still comes from the shared `[scheduler]` config for all themes; only
the theme and its topic history are per-invocation.

## How topic selection avoids repeats

Each run calls the LLM once to invent a specific topic within its
theme, telling it the last `topic_history_size` topics *for that same
theme* to avoid repeating (stored in
`storage/topic_history_<theme-slug>.json`, one file per theme, managed
automatically - `app/services/topic_history.py`). Themes don't share
history with each other, so "educational" topics never steer
"political satire" away from a good idea and vice versa. This is a
simple steering mechanism, not a guarantee of novelty - the LLM can
still occasionally produce something similar to an older topic further
back than the history window.

## Output resolution

`output_resolution_short_side` (750 by default here) scales the final
rendered video down after everything else is composited (footage,
subtitles, audio) - it does not change what resolution stock footage is
searched for, so it can't cause Pexels/Pixabay searches to come up
empty. Set it to `0` or remove it to export at native resolution
(1080p+) instead.

## Failure behavior

- If topic generation or the video render itself fails, the script exits
  non-zero and logs why - your cron/Railway job's own failure
  notifications (if any) will catch this.
- If the video renders successfully but a *publish* (YouTube/Instagram)
  fails, the script still exits **0** - the video was produced
  successfully, publishing is a separate concern. Check the logs for the
  specific publish error.
