# Running the LLM for $0/mo (Ollama on Railway)

This is the genuinely-free path for script/topic generation, as
opposed to a metered API like OpenAI/Groq/Anthropic. Ollama runs as its
own private service inside your Railway project - it's Railway compute
you're already paying for as part of hosting, not a separate bill.

It's also the deliberate alternative to `g4f` (the other $0 option):
g4f is an unofficial wrapper around other services' free tiers without
their authorization, and can break or get shut off without warning.
Ollama is a real, supported, self-hosted model - slower per-request and
needs its own Railway service, but doesn't carry that risk.

## Step 1: Deploy Ollama as a Railway service

Railway has an official one-click template:
[railway.com/deploy/ollama-railway](https://railway.com/deploy/ollama-railway)

This deploys the official `ollama/ollama` Docker image with a 5GB
volume for model storage. **It gets no public domain by design** -
Ollama has no built-in authentication, so a public URL would be an
open endpoint anyone could spend your Railway compute on. It's only
reachable from other services in the same Railway project, at:

```
http://<service-name>.railway.internal:11434
```

(`<service-name>` is whatever you named the service when deploying -
`ollama` by default, matching the `config.example.toml` default.)

## Step 2: Pull a model

The image starts with zero models installed. From a shell with access
to your Railway project's private network (e.g. Railway's own shell
for another service in the project), pull one:

```bash
curl http://ollama.railway.internal:11434/api/pull -d '{"model":"llama3.2:1b"}'
```

**Model size is a real cost/quality tradeoff, since it's RAM your
Railway service has to have:**

| Model | Approx. RAM needed | Quality for short scripts |
|---|---|---|
| `llama3.2:1b` (default here) | ~1-2GB | Basic but usable for short (60-90s) video scripts |
| `llama3.2:3b` | ~2-3GB | Noticeably better, still cheap |
| `gemma3:4b` | ~3-4GB | Good quality, still runs on modest hardware |

Start with `llama3.2:1b` (the config default) - it's the cheapest, and
script-writing for a 60-90 second video is a simple enough task that a
1B model is often sufficient. Upgrade to `3b` or `gemma3:4b` if the
output quality isn't good enough, by pulling the new model (same `curl`
command, different `model` value) and updating
`config.toml`'s `ollama_model_name`.

## Step 3: Configure the app

Already the default in `config.example.toml`:

```toml
[app]
llm_provider = "ollama"
ollama_base_url = "http://ollama.railway.internal:11434/v1"
ollama_model_name = "llama3.2:1b"
```

If you named the Railway service something other than `ollama`, change
`ollama_base_url` to match (`http://<your-service-name>.railway.internal:11434/v1`).

## Verifying it works

From another service in the same Railway project (e.g. the main app's
shell):

```bash
curl http://ollama.railway.internal:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:1b","messages":[{"role":"user","content":"Say hello"}]}'
```

A JSON response with a `choices[0].message.content` field means it's
working - this is the same OpenAI-compatible endpoint shape
`app/services/llm.py` already calls for the `ollama` provider.

## This only covers the LLM

TTS (Edge TTS) and stock footage (Pexels/Pixabay/Coverr) are already
$0/mo by default elsewhere in this config - see
`docs/scheduled-publishing.md`'s cost section. With Ollama added, the
only thing left with a real bill is Railway itself, which was the
explicit goal.
