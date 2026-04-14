# agent_demo

`agent_demo/` is an isolated, repository-aware demo module inside Elevia.
It reads one real offer from the repository in read-only mode, combines it with one candidate CV/profile text, and produces a recruiter-facing markdown fit report using LangChain + OpenAI.

## What this demo does

The demo is designed to feel operational without exposing Elevia's proprietary core.

Input:
- one real offer from `apps/api/data/db/offers.db`
- one candidate CV/profile text file

Output:
- a markdown report with these fixed sections:
  - `# Role Summary`
  - `# Candidate Summary`
  - `# Relevant Overlaps`
  - `# Gaps / Weaker Signals`
  - `# Recommended Positioning`
  - `# CV Improvement Suggestions`
  - `# Final Assessment`

## What real repository data it uses

The demo uses Elevia's existing SQLite offer store in read-only mode:
- `apps/api/data/db/offers.db`
- table: `fact_offers`

It does not dump the dataset.
It loads one offer at a time by ID or the latest available offer for a given source.

## What it intentionally does not use

To protect the proprietary core, the demo does not call or expose:
- core matching logic
- scoring formulas
- ranking weights
- internal candidate ranking internals
- proprietary decision thresholds

The demo is a lightweight analysis layer, not the Elevia product engine.

## Environment handling

The demo follows the repository's existing API environment convention:
- it loads `apps/api/.env` if present
- it reads `OPENAI_API_KEY`
- it also accepts legacy `LLM_API_KEY` if already present in the environment

If no API key is available, the demo exits with a clear error message.

## Install

Use the repository virtualenv when possible.

```bash
./.venv/bin/pip install -r agent_demo/requirements.txt
```

## Run

List recent real offers:

```bash
./.venv/bin/python agent_demo/main.py --list-offers --limit 5
```

Run the demo against the latest Business France offer:

```bash
./.venv/bin/python agent_demo/main.py --cv agent_demo/sample_cv.txt
```

Run it against a chosen offer:

```bash
./.venv/bin/python agent_demo/main.py --offer-id BF-237974 --cv agent_demo/sample_cv.txt
```

Save to a chosen file:

```bash
./.venv/bin/python agent_demo/main.py \
  --offer-id BF-237974 \
  --cv agent_demo/sample_cv.txt \
  --out agent_demo/output_real.md
```

## Run tests

```bash
./.venv/bin/python -m pytest -q agent_demo/tests
```

## File layout

```text
agent_demo/
├── agent.py
├── data_loader.py
├── llm_client.py
├── main.py
├── output_example.md
├── prompts.py
├── requirements.txt
├── sample_cv.txt
└── tests/
```

## Design choices

- `data_loader.py`
  - read-only SQLite access to real offers already stored in the repo
- `llm_client.py`
  - OpenAI via `langchain-openai`, aligned with the existing repo env pattern
- `agent.py`
  - simple two-step LangChain flow:
    - structured extraction
    - recruiter-facing fit analysis
- `tests/`
  - validate loading, formatting, and graceful failure paths without live LLM calls

## Why this is credible in a demo

This module proves:
- clean Python execution inside a larger repository
- safe reuse of real internal data sources
- LangChain orchestration with a real OpenAI model
- recruiter-readable output
- engineering discipline through tests and explicit boundaries
