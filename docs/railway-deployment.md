# Deploying to Railway

MoneyPrinterTurbo ships two processes from the same codebase:

- **webui** — the Streamlit UI (default)
- **api** — the FastAPI backend (`main.py`)

Both are built from the same `Dockerfile` and started by `start.sh`, which
picks the process from the `SERVICE` environment variable and binds
whichever port Railway assigns via `$PORT`.

## 1. Deploy the WebUI

1. Create a new Railway project from this GitHub repo.
2. Railway detects `railway.toml` and builds with the repo's `Dockerfile`.
   No extra configuration is needed — `SERVICE` defaults to `webui`.
3. Once deployed, open the generated Railway URL; you'll land on the
   Streamlit UI.

## 2. (Optional) Deploy the API as a second service

If you also want the FastAPI backend reachable (e.g. for the `/docs`
endpoint or programmatic access):

1. In the same Railway project, add a second service from the same repo.
2. Set its **Start Command** (Settings → Deploy) to `./start.sh`.
3. Add an environment variable `SERVICE=api` on that service.
4. Optionally change its healthcheck path to `/docs` (Settings → Deploy →
   Healthcheck Path) — `railway.toml`'s default of `/` is tuned for the
   webui service.

## Persisting configuration

The app reads secrets and provider settings (API keys, LLM provider,
etc.) from `config.toml` at the repo root, which is copied from
`config.example.toml` on first boot if missing. Railway's filesystem is
ephemeral between deploys, so any changes made through the WebUI's
settings panel will be lost on redeploy unless you either:

- Attach a [Railway volume](https://docs.railway.com/reference/volumes)
  mounted at `/MoneyPrinterTurbo` and edit `config.toml` through it, or
- Commit your configured `config.toml` to a private fork/branch instead of
  relying on `config.example.toml`.

## Environment variables

| Variable  | Default | Purpose                                                        |
| --------- | ------- | ---------------------------------------------------------------- |
| `PORT`    | `8501`  | Set automatically by Railway; the port `start.sh` binds.          |
| `SERVICE` | `webui` | Which process to run: `webui` or `api`.                           |

All other configuration (LLM provider keys, TTS, stock-footage providers,
etc.) is still managed via `config.toml`, not environment variables — see
`config.example.toml` for the full list of settings.

## Local equivalent

You can exercise the same entry point locally without Railway:

```bash
# webui on port 8501
./start.sh

# api on port 8080
SERVICE=api PORT=8080 ./start.sh
```
