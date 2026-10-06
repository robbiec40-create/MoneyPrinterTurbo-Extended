# Auto-publishing to Instagram (Reels)

This lets a finished video get published straight to your Instagram
account as a Reel after rendering.

**Good news for personal use:** since you're publishing to your own
Instagram account (not serving other people's accounts), Meta's
"Standard Access" tier works immediately, with no App Review wait - that
multi-week review is only required to serve accounts you don't personally
manage. Setup here is mostly free and fast; the slow part (if any) is
just converting your account type if it isn't already Business.

## Key differences from the YouTube integration

- **Instagram needs a public URL, not a file upload.** Its API fetches
  the video from a URL you give it - it doesn't accept uploaded bytes
  directly like YouTube does. This app already serves rendered videos
  publicly (via its FastAPI server's `/tasks` route), so you just need to
  tell it what your server's public URL is (`public_base_url`).
- **No permanent refresh token.** YouTube's token lasts indefinitely;
  Instagram's long-lived token expires after ~60 days and needs
  re-generating periodically (same script, re-run).
- **Reels are capped at 90 seconds** via the API, and **always public**
  (no "unlisted" or "private" option for Reels published this way).

## Step 1: Instagram account requirements

1. Your Instagram account must be a **Business** account (Creator
   accounts don't work for API publishing). Convert in the Instagram
   app: Settings → Account type and tools → Switch to professional
   account → Business.
2. It must be **linked to a Facebook Page** you manage (Instagram
   prompts for this during the Business conversion, or you can link one
   later in Instagram's settings).

## Step 2: Create a Meta app

1. Go to [developers.facebook.com](https://developers.facebook.com/) →
   **My Apps** → **Create App**. Choose a "Business" app type.
2. Add the **Instagram Graph API** product to the app.
3. In **App Roles → Roles**, confirm your own Facebook account is listed
   as an Admin/Developer on this app (it is, by default, as the creator)
   - this is what unlocks Standard Access for your own account without
   App Review.

## Step 3: Get a short-lived token, then exchange it

1. Go to the [Graph API
   Explorer](https://developers.facebook.com/tools/explorer/), select
   your app, and generate a **User Token** with these permissions:
   `instagram_business_basic`, `instagram_business_content_publish`.
2. Copy that token (it's short-lived, ~1 hour) and your app's **App ID**
   and **App Secret** (App Dashboard → Settings → Basic).
3. Exchange it for a long-lived token and look up your Instagram
   Business Account ID:

   ```bash
   python scripts/instagram_auth.py \
     --app-id YOUR_APP_ID \
     --app-secret YOUR_APP_SECRET \
     --short-lived-token TOKEN_FROM_GRAPH_API_EXPLORER
   ```

   This prints a long-lived `access_token` (lasts ~60 days) and your
   `ig_user_id`.

## Step 4: Configure the app

```toml
[app]
# Wherever your FastAPI server (main.py) is reachable from the internet -
# e.g. your Railway domain. Instagram's servers fetch the rendered video
# from here, so it must be a real public HTTPS URL, not localhost.
public_base_url = "https://your-app.up.railway.app"

[instagram]
access_token = "..."   # from scripts/instagram_auth.py
ig_user_id = "..."     # from scripts/instagram_auth.py
```

## Step 5: Enable it per video

In the WebUI, under **Publishing**, check **Auto-publish to Instagram
(Reel)** and optionally set a caption (falls back to the video subject
if left blank).

## Keeping the token alive

Instagram's long-lived token expires after ~60 days. Before it does,
get a fresh short-lived token from the Graph API Explorer and re-run
`scripts/instagram_auth.py` to get a new 60-day token, then update
`config.toml`. There's no way around this periodic refresh - Meta
doesn't offer a permanent refresh token the way Google does for
installed apps.

## Notes

- **A failed publish doesn't fail the render** - the video is still
  saved locally; check the logs for the specific error.
- **Political/satire content**: like other platforms, Instagram applies
  extra scrutiny to political content for distribution/monetization -
  independent of this upload integration.
- If `public_base_url` points at a server that isn't actually reachable
  from the internet (e.g. you're running this locally without a tunnel
  or deployment), Instagram's fetch will simply fail - this isn't
  something the app can detect in advance, only when the publish is
  attempted.
