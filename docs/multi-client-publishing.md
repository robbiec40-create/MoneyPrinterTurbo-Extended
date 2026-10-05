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

## Scheduling each client

One cron/Railway Cron entry per client, using `--client` instead of
`--theme`:

```bash
python scripts/scheduled_video_job.py --client client1
```

See `docs/scheduled-publishing.md`'s Railway Cron / OS cron tables for
the actual schedule syntax (UTC conversion, DST caveat, etc.) - the only
difference here is the Start Command uses `--client <id>` instead of
`--theme "..."`.

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
