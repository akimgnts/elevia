# Elevia

Elevia is a repository-aware AI job matching and application preparation system.
It parses candidate profiles, structures offer data, surfaces relevant opportunities, and generates recruiter-ready application materials.
The public-facing demo entry point is `agent_demo/`, which runs a safe LangChain analysis against one real offer stored in the repository.
The core matching and scoring internals remain intentionally protected.

## What problem this project solves

Recruiting workflows break when candidate data, offer data, and application preparation live in separate tools.
Elevia brings them into one system:
- parse and enrich a candidate profile
- normalize and structure job offers
- surface relevant opportunities
- prepare CV and application artifacts from the same underlying profile context

## What the system does

At a high level, the repository contains:
- a backend API for profile parsing, offer access, inbox/matching flows, and document generation
- a web application for profile, cockpit, inbox, offers, market, and application tracking workflows
- a recruiter-facing `agent_demo/` module that uses one real internal offer in read-only mode with LangChain + OpenAI
- supporting referentials and datasets used for parsing and normalization

This repository does **not** expose proprietary ranking rules or scoring weights in its public-facing documentation.

## Architecture

```text
apps/
├── api/        # FastAPI backend, parsing pipelines, offer access, documents
└── web/        # React/Vite frontend

agent_demo/     # Recruiter-facing LangChain demo using one real offer read-only
scripts/        # Operational scripts and dev tooling
scripts/archive/root_legacy/   # Archived one-off legacy scripts moved out of root

docs/           # Product, architecture, sprint, and archive documentation
data/           # Runtime-free datasets, snapshots, and archived historical exports
labs/           # Experimental notebooks and archived analysis work
```

## Main components

### `apps/api`
Core backend system.

Key responsibilities:
- CV/profile parsing and normalization
- offer catalog access from internal SQLite stores
- inbox and application-tracker endpoints
- CV and letter generation pipelines
- market insight and context routes

Primary entry point:
- `apps/api/src/api/main.py`

### `apps/web`
Product UI.

Key areas:
- `Analyze`
- `Profile`
- `Cockpit`
- `Inbox`
- `Offers`
- `Candidatures`
- `Market`

Primary entry point:
- `apps/web/src/main.tsx`

### `agent_demo`
A lightweight recruiter-facing demo designed to be understood quickly.

What it does:
- reads one real offer from `apps/api/data/db/offers.db` in read-only mode
- reads one candidate CV/profile text file
- runs a structured LangChain + OpenAI fit analysis
- returns a clean markdown report

This is the fastest way for a recruiter or reviewer to see a concrete AI workflow without exposing proprietary matching internals.

## Tech stack

- Python
- FastAPI
- React + Vite + TypeScript
- SQLite
- LangChain Python
- OpenAI
- pytest

## Quick start

### 1. Create and install the Python environment

```bash
make venv
make install
```

### 2. Start the product locally

```bash
make dev-up
```

This starts:
- API: `http://localhost:8000`
- Web: `http://localhost:3001`

### 3. Run the recruiter demo

List recent real offers:

```bash
make agent-demo-list
```

Run the demo against the latest offer with the bundled sample CV:

```bash
make agent-demo-run
```

Run the demo tests:

```bash
make agent-demo-test
```

## Recruiter entry point

If you only want the fastest path to evaluating the repository:
- open `agent_demo/README.md`
- run `make agent-demo-list`
- run `make agent-demo-run`
- review `agent_demo/output_example.md`

That path is intentionally isolated, real, and safe.

## Design principles

- One repository, clear boundaries
- Real data where safe, synthetic data only when necessary
- Read-only access for demos
- Deterministic core workflows where possible
- Protected proprietary logic
- Small, testable modules over fake complexity
- Product workflows over disconnected experiments

## What is intentionally not exposed

To keep the repository safe to share publicly, the following are intentionally not surfaced as public demo logic:
- proprietary matching internals
- scoring weights and calibration rules
- internal ranking heuristics
- full production data dumps
- secrets and runtime credentials

## Repository hygiene decisions

This cleanup intentionally moved legacy noise out of the root directory into archive locations:
- historical root scripts → `scripts/archive/root_legacy/`
- historical root notes/docs → `docs/archive/root_legacy/`
- historical root data exports → `data/archive/root_legacy/`
- historical root notebooks → `labs/archive/root_notebooks/`

The goal is simple: the root should explain the project, not obscure it.
