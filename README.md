# AI Lab v1

AI Lab is an event-sourced autonomous research environment with a local-first desktop UI.

## Stack

- Desktop: Electron + React + TypeScript
- API: FastAPI + SQLAlchemy + PostgreSQL
- Worker: Dramatiq workers over Redis
- Sandbox: FastAPI + ephemeral Docker tool execution
- Storage: Event log as source of truth + projection tables
- Deployment: Docker Compose (single VM/local)

## Monorepo layout

- `apps/desktop`: Electron desktop application
- `services/api`: FastAPI command/query API and websocket streams
- `services/worker`: Queue workers and autonomous agent loop
- `services/sandbox`: Policy-enforced sandbox service for tool execution
- `packages/domain`: Shared Python domain schemas and event definitions
- `packages/policy`: Tool policy schemas and enforcement defaults
- `infra/docker`: Compose and container assets
- `infra/migrations`: SQL migrations
- `ops`: operational scripts

## Quick start

### 1) Start infra and services (API + worker + sandbox + Postgres + Redis)

```bash
cd /Users/joshmalone/Code/projects/ai-lab
docker compose -f infra/docker/docker-compose.yml up --build
```

API is available at `http://localhost:8000`.

### 2) Run desktop app (in a separate terminal)

```bash
cd /Users/joshmalone/Code/projects/ai-lab/apps/desktop
npm install
npm run dev
```

### 3) Run tests

```bash
cd /Users/joshmalone/Code/projects/ai-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/domain -e packages/policy -e services/api -e services/worker -e services/sandbox pytest
python3 -m pytest -q
```

## Core principles implemented

1. Events are the source of truth.
2. World state is reducer-derived and replayable.
3. Experiments and experiment runs are separate objects.
4. Agent runtime is stateless, trace-driven.
5. Critic/evaluator feeds planner direction.
6. Tool execution is autonomous but policy constrained.
