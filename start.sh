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
