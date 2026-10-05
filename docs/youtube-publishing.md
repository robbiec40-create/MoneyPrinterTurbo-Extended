# Auto-publishing to YouTube

This lets a finished video get uploaded straight to your YouTube channel
after rendering, instead of you downloading and uploading it by hand.

It's a one-time setup (10-15 minutes), done once per YouTube channel, not
per video.

## Why this needs OAuth (not just an API key)

Uploading a video on your behalf requires Google to confirm you
authorized it — a simple API key isn't enough for write access to a
channel. The setup below creates a long-lived credential ("refresh
token") that this app reuses for every future upload, so you only log in
once.

## Step 1: Create a Google Cloud OAuth app

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or pick an existing one).
3. **APIs & Services → Library** → search "YouTube Data API v3" → **Enable**.
4. **APIs & Services → OAuth consent screen**:
   - User type: **External**.
   - Fill in the required app name/contact fields.
   - Under **Test users**, add your own Google account's email. While the
     app is in "Testing" status (the default, and fine for personal use),
     only accounts listed here can authorize it — you don't need Google
     to review/verify the app for your own channel to work.
5. **APIs & Services → Credentials** → **Create Credentials** → **OAuth
   client ID**:
   - Application type: **Desktop app**.
   - Download the resulting JSON — this is your `client_secret.json`.

## Step 2: Generate your token (once, on a machine with a browser)

This step needs a real browser, so run it on your laptop, not on a
headless server — even if the server is where the app actually runs.

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

python scripts/youtube_auth.py \
  --client-secrets /path/to/client_secret.json \
  --token-out token.json
```

A browser window opens asking you to log into the Google account that
owns the YouTube channel, and to grant upload permission. Once you
approve it, `token.json` is written — this is the credential the server
will reuse for every upload from now on, without logging in again.

**Keep `token.json` secret** — anyone with it can upload to your channel.
Don't commit it (it's already in `.gitignore`).

## Step 3: Point the server at both files

Copy `client_secret.json` and `token.json` to wherever your server (or
Docker/Railway volume) can read them, then in `config.toml`:

```toml
[youtube]
client_secrets_file = "/path/to/client_secret.json"
token_file = "/path/to/token.json"
```

## Step 4: Enable it per video

In the WebUI, under **Publishing**, check **Auto-publish to YouTube** and
fill in a title/description/tags (or leave them blank to fall back to the
generated video subject/script). Submitting the form will now upload
each rendered video to your channel automatically.

## Notes

- **Made for Kids (COPPA)**: set this accurately — it's a legal
  requirement, not a style preference. Default is unchecked (not made
  for kids).
- **Unverified app limits**: while your OAuth app is in Google's
  "Testing" status, only the test users you listed in Step 1 can
  authorize it, and tokens may need periodic re-authorization depending
  on Google's current policy for testing apps. For your own channel this
  is normally not an issue; if you want other people's channels to use
  this too, you'd need to submit the app for Google's verification
  review.
- **Political/satire content**: YouTube (like other platforms) applies
  extra scrutiny to political content — monetization eligibility and
  distribution can be affected independent of this upload integration.
- **A failed upload doesn't fail the render** — if YouTube rejects the
  upload (quota, auth expired, etc.), the video is still saved locally;
  check the logs for the specific error.
