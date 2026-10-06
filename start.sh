#!/bin/sh
# Entry point used by Docker/Railway deployments.
#
# Railway (and similar PaaS platforms) assign a dynamic port via the
# $PORT environment variable and require the app to bind 0.0.0.0, so this
# script wires that through to whichever process this deployment runs.
#
# Which process to start is picked with $SERVICE:
#   SERVICE=webui (default) -> Streamlit UI
#   SERVICE=api             -> FastAPI/uvicorn backend (main.py)
set -e

SERVICE="${SERVICE:-webui}"
PORT="${PORT:-8501}"

# Write credential secrets from env vars to disk at boot, since config.toml
# only stores file paths (see config.example.toml's [youtube]/[instagram]
# sections). This lets Railway hold the actual secret content as encrypted
# env vars instead of it living in a volume or the repo. Re-written on every
# boot, so a rotated token just needs the Railway variable updated.
if [ -n "$YOUTUBE_CLIENT_SECRET_JSON" ] || [ -n "$YOUTUBE_TOKEN_JSON" ]; then
  mkdir -p /MoneyPrinterTurbo/credentials
  [ -n "$YOUTUBE_CLIENT_SECRET_JSON" ] && printf '%s' "$YOUTUBE_CLIENT_SECRET_JSON" > /MoneyPrinterTurbo/credentials/youtube_client_secret.json
  [ -n "$YOUTUBE_TOKEN_JSON" ] && printf '%s' "$YOUTUBE_TOKEN_JSON" > /MoneyPrinterTurbo/credentials/youtube_token.json
fi

case "$SERVICE" in
  api)
    # main.py reads its port from $PORT / config.toml (see app/config/config.py)
    export PORT
    exec python3 main.py
    ;;
  webui|*)
    exec streamlit run ./webui/Main.py \
      --server.address=0.0.0.0 \
      --server.port="$PORT" \
      --server.enableCORS=true \
      --browser.gatherUsageStats=false
    ;;
esac
