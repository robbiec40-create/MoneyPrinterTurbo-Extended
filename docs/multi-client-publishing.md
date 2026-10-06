# Multi-client publishing

Each client gets exactly one theme and their videos post to **their
own** YouTube/Instagram accounts - not yours. This is a different mode
from the single-owner scheduling in `docs/scheduled-publishing.md`
(which uses your own accounts for every theme); read that doc first if
you haven't, since this one builds on it.

## Why this needs a credential per client

YouTube and Instagram's APIs authorize a specific account, not "whoever
is running this server." There's no way to upload to a client's channel
without a credential that client themselves produced by logging into
their own account - that's the whole point of OAuth. So onboarding a
client means they (or you, acting with something they gave you)
complete that platform's one-time auth setup, and you end up holding a
credential scoped to just their account.

## Onboarding a new client

For each client, repeat the relevant parts of
`docs/youtube-publishing.md` and/or `docs/instagram-publishing.md`,
**but save the resulting files under a name that identifies the
client**, e.g.:

```bash
# YouTube - run on a machine with a browser, logged into the CLIENT's Google account
python scripts/youtube_auth.py \
  --client-secrets client_secret.json \
  --token-out credentials/client1_youtube_token.json

# Instagram - after the client gives you a short-lived Graph API Explorer
# token from THEIR Meta app/account
python scripts/instagram_auth.py \
  --app-id CLIENT_APP_ID \
  --app-secret CLIENT_APP_SECRET \
  --short-lived-token CLIENT_SHORT_LIVED_TOKEN
# -> copy the printed access_token/ig_user_id into this client's config block
```

Who actually clicks through the OAuth consent screen matters: it has to
be the client logging into their own account (YouTube), or someone with
admin access to the client's Meta app/Business account (Instagram). You
can walk them through it over a screen share, or have them run the
script themselves and send you the resulting `token.json` - either
works, since the script itself doesn't know or care who runs it.

**You are now holding credentials that can post to someone else's
channel.** Treat `credentials/*.json` and the `instagram_access_token`
values with the same care as any other secret - keep them out of git
(already covered by `.gitignore`'s `client_secret*.json`/`token.json`
patterns; if you rename files per-client as suggested above, make sure
your naming still matches those patterns, or extend `.gitignore`), and
only give yourself access to a client's credential for as long as
you're actually running their account.

## Adding the client to config.toml

```toml
[[clients]]
id = "client1"
theme = "political satire"            # this client's ONE theme
youtube_token_file = "credentials/client1_youtube_token.json"
youtube_privacy_status = "public"
instagram_access_token = "..."
instagram_ig_user_id = "..."
```

Leave out `youtube_token_file` if this client only wants Instagram, or
leave out the `instagram_*` fields if they only want YouTube - a client
missing a platform's credentials just doesn't publish to that platform
(logged, not an error).

Optional per-client overrides (video source, voice, aspect ratio,
resolution) - omit any of these and it falls back to `[scheduler]`'s
shared default:

```toml
video_source = "pexels"
voice_name = "en-US-AriaNeural-Female"
video_aspect = "9:16"
paragraph_number = 1
output_resolution_short_side = 750
```

## Scheduling each client (and pricing tiers)

**A client's frequency/tier is entirely a matter of how many
cron/Railway Cron entries you set up for them** - there's no count or
frequency flag on the script itself. Each entry just runs:

```bash
python scripts/scheduled_video_job.py --client client1
```

This was verified to work correctly run back-to-back for the same
client: each run gets its own task ID (no collisions), and topic
history is re-read fresh each invocation, so the Nth run of the day
correctly avoids repeating what the 1st through (N-1)th runs already
picked - there's no in-memory state carried between runs to worry
about, since each invocation is a separate process.

| Tier | Cadence | Monthly price | Annual price (billed yearly) | Cron entries (8am ET example, i.e. `12:00 UTC` now - see the EDT/EST note in `docs/scheduled-publishing.md`) |
|---|---|---|---|---|
| Starter Plan | ~16 videos/mo (4x/week - no clean weekly cadence lands exactly on 16, this is the closest) | $19/mo | **$13/mo** | One entry: `0 12 * * 1,2,4,6` (Mon/Tue/Thu/Sat, ~17/mo) |
| Creator Plan | 1x/day | $33/mo (not yet updated in Stripe - still charges $39 live) | **$24/mo** | One entry: `0 12 * * *` |
| Pro | 2x/day | $57/mo (no Stripe product yet) | **$40/mo** (no Stripe product yet) | Two entries, spaced through the day, e.g. `0 12 * * *` and `0 0 * * *` (8am and 8pm ET) |

Margin is essentially unaffected by price within this range - variable
cost per video is a fraction of a cent (see the per-video cost
breakdown discussed when this pricing was set) - so these prices are a
competitiveness decision, not a cost one. **Starter's $19/mo is
confirmed live in Stripe; Creator's target price ($33) is NOT yet
live - the Stripe product still charges $39 until it's updated there**
(this doc can't update Stripe itself - see the Stripe section
earlier in this conversation for why). Creator and Pro's monthly
prices ($33, $57) undercut Faceless.video's own monthly rates by $2
(their Daily $35, Double $59); annual prices undercut their annual
rates by at least $1/mo (their Starter $14, Daily $25, Double $41) -
both are direct competitor undercuts, not independently-derived
discounts. Neither the Pro tier nor any annual price has a live
Stripe product yet - fill them in here once they exist, and record
each client's actual price (and whether they're on monthly or annual
billing) via `monthly_price_usd` in that client's `[[clients]]` block.

For Railway, each entry is its own Cron Job service (all pointing at
this same client's `--client <id>` Start Command). For OS cron, they're
just additional lines in the crontab. See `docs/scheduled-publishing.md`
for the full Railway/OS cron setup and the UTC/DST conversion details -
nothing about multi-entry scheduling is different there, you're just
adding more entries per client instead of one.

Set `videos_per_day` in that client's `[[clients]]` block to whatever
their tier implies (e.g. `0.43` for 3x/week, `1` or `2`) - this is
**informational only**, so you have the tier recorded next to the
client's other settings; it does not create schedules by itself.

## How this differs from single-owner mode under the hood

- `--theme` (or no flag): publishes via the global
  `[youtube]`/`[instagram]` config - your own accounts, same as
  `docs/youtube-publishing.md`/`docs/instagram-publishing.md` describe.
- `--client <id>`: looks up that client's `[[clients]]` entry, and
  **task.py's own publish step is explicitly disabled** for that run
  (`youtube_auto_publish`/`instagram_auto_publish` are forced `False` in
  the `VideoParams` sent to the renderer) - publishing happens
  afterward, directly from `scheduled_video_job.py`, passing that
  client's specific `token_file`/`access_token`/`ig_user_id` into
  `youtube.upload_video()`/`instagram.upload_reel()`. This is what
  guarantees a client's video can never accidentally post through your
  own global credentials, or another client's.
- Topic history is kept per client (`storage/topic_history_<client
  id>.json`), not per theme - two clients with the same theme (two
  "bedtime stories" clients, say) each get their own history, so one
  doesn't block the other from a topic just because it's already
  covered elsewhere.

## Removing a client

Delete their `[[clients]]` block, delete their cron/Railway Cron Job
entry, and delete their credential files. Their `storage/topic_history_
<id>.json` is harmless to leave behind, but delete it too if you want a
clean slate should they ever come back.
