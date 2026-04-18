# agents_runtime

`agents_runtime/` is the external AI runtime layer that sits above the Elevia repo.

It is intentionally **not** part of `apps/api`.
The repo remains responsible for:
- deterministic CV parsing
- references and registries
- product data structures
- frontend and API contracts

This runtime is responsible for:
- real LLM-backed agents
- API key usage
- autonomous reasoning on top of deterministic outputs
- future orchestration across multiple agents

## First agent included

The first concrete runtime is:

- `cv_understanding_agent`

Its job is to:
- consume profile-understanding input prepared from the repo
- reason over CV structure, deterministic signals, and references
- infer structured `skill_links`
- produce targeted confirmation questions
- return a response compatible with the profile-understanding session contract

## Why this exists

This folder fixes the architectural problem where “AI” behavior was being simulated too close to the repo.

The runtime here is:
- LLM-backed
- API-key driven
- callable over HTTP
- ready to become part of a future team of agents

## Environment

This runtime loads `apps/api/.env` if present and expects:

```bash
OPENAI_API_KEY=...
LLM_MODEL=gpt-4o-mini
```

`OPENAI_API_KEY` is required.

## Install

```bash
pip install -r agents_runtime/requirements.txt
```

## Run the server

```bash
python -m uvicorn agents_runtime.cv_understanding_agent.server:app --reload --port 8091
```

## Call the agent directly

Health check:

```bash
curl http://127.0.0.1:8091/health
```

Profile understanding session:

```bash
curl -X POST http://127.0.0.1:8091/profile-understanding/session \
  -H "Content-Type: application/json" \
  -d @agents_runtime/cv_understanding_agent/sample_request.json
```

## Connect the repo to this runtime

In the repo environment:

```bash
ELEVIA_PROFILE_UNDERSTANDING_PROVIDER=http
ELEVIA_PROFILE_UNDERSTANDING_URL=http://127.0.0.1:8091/profile-understanding/session
```

This lets `apps/api/src/profile_understanding/service.py` call the external runtime instead of the repo-side stub.

## Safe rollout behavior

The repo-side integration is intentionally safe by default:

- if `ELEVIA_PROFILE_UNDERSTANDING_PROVIDER` is not set, the repo stays on `stub`
- if `ELEVIA_PROFILE_UNDERSTANDING_PROVIDER=http` but the external runtime is unavailable, the repo falls back to `stub`

Optional stricter controls:

```bash
ELEVIA_PROFILE_UNDERSTANDING_ALLOW_STUB_FALLBACK=0
ELEVIA_PROFILE_UNDERSTANDING_HTTP_TIMEOUT_SECONDS=20
```

Recommended usage:

- local/dev:
  - `ELEVIA_PROFILE_UNDERSTANDING_PROVIDER=http`
  - `ELEVIA_PROFILE_UNDERSTANDING_URL=http://127.0.0.1:8091/profile-understanding/session`
  - keep fallback enabled

- VPS / production rollout:
  - enable the external runtime only when it is running and monitored
  - keep fallback enabled during the first rollout
  - disable fallback only after you explicitly want fail-closed behavior

## File layout

```text
agents_runtime/
├── README.md
├── requirements.txt
└── cv_understanding_agent/
    ├── __init__.py
    ├── agent.py
    ├── config.py
    ├── contracts.py
    ├── main.py
    ├── prompts.py
    ├── repository_adapter.py
    ├── sample_request.json
    └── server.py
```

## What is intentionally not included

- multi-agent orchestration
- LangGraph runtime
- LangSmith observability
- memory persistence
- tool calling beyond repo context shaping

Those come next.
This first runtime is meant to be:
- real
- clean
- LLM-backed
- externally callable
- ready to plug into a future orchestrator
