---
skill: project-feature
status: review-ready
date: 2026-08-29
title: Auto-seed inner agents on backend startup
---

# Change Design: Auto-seed inner agents on backend startup

## Goal

Replace the manual `setup_cs_agents.py` script with automatic agent
creation at backend startup, so the "Customer Service Agent" and its
4 pipeline sub-agents are always available without any extra step.

## Background

Currently, after starting the backend, the user must manually run:

    python setup_cs_agents.py --user-id kids

This creates 4 pipeline sub-agents via HTTP API calls. The
"Customer Service Agent" itself must also be created separately via
the UI or API. This is error-prone and doesn't work in Docker/CI
without extra orchestration.

## Implementation Plan

### 1. New file: `examples/agent_service/_seed_agents.py`

A single async function `seed_inner_agents(storage, user_id)` that:

- Defines all 5 inner agent definitions (Customer Service Agent + 4
  pipeline sub-agents) as a module-level constant `INNER_AGENTS`
- Calls `storage.list_agents(user_id)` to get existing agents
- Filters by name to find which are missing
- Creates missing agents via `storage.upsert_agent()` directly
  (bypassing HTTP — no need for the server to be listening)
- Logs what was created vs. skipped

### 2. Modify: `examples/agent_service/main.py`

Wrap the framework's lifespan context to seed agents **after** storage
and other resources are entered (the original lifespan opens the Redis
connection, message bus, etc.):

- Import `seed_inner_agents` from `_seed_agents`
- Define `_INNER_AGENT_USER_ID` from env var (default `"inner"`)
- Wrap `app.router.lifespan_context` with an `asynccontextmanager` that
  calls `seed_inner_agents()` after the original lifespan enters, before
  the first request is served
- Uses the modern lifespan API (no `@app.on_event("startup")` deprecation)

### 3. Refactor: `examples/agent_service/setup_cs_agents.py`

- Keep the file for development/testing reference
- Import `INNER_AGENTS` from `_seed_agents.py` to avoid duplication
- The script still works via HTTP for backward compatibility

### 4. Single source of truth for prompts

The `INNER_AGENTS` constant in `_seed_agents.py` becomes the canonical
definition. The prompts in `cs_pipeline_agent.py`
(`_ANALYZER_PROMPT`, `_SOLVER_PROMPT`, `_REVIEWER_PROMPT`) are used
by the streaming pipeline at runtime — they stay where they are
because they serve a different purpose (runtime sub-agent creation
vs. persisted agent records).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| User ID for inner agents | Env var `INNER_AGENT_USER_ID`, default `"inner"` | Configurable, doesn't collide with real users |
| Storage layer vs. HTTP API | Storage layer (`upsert_agent`) | No HTTP dependency, works before server listens |
| Idempotency strategy | List → filter by name → create missing | Simple, safe on restart |
| `setup_cs_agents.py` fate | Keep, refactor to import from `_seed_agents` | Backward compat, dev tool |
| Prompt duplication | Accept: `_seed_agents.py` for persisted records, `cs_pipeline_agent.py` for runtime | Different lifecycles, different consumers |

## Complexity Assessment

| Dimension | Value |
|-----------|-------|
| New/modified files | 3 (1 new + 2 modified) |
| DB/API changes | No |
| Frontend | No |
| Cross-module | No |

**Complexity: S (Simple)**

Per the skill rules, S complexity runs Phase 1-5 + Phase 8 + Phase 9,
skipping Phase 6 and Phase 7. However, since the user said "all next
phases go ahead", we will run all phases for completeness.

## Impact Summary

- `examples/agent_service/_seed_agents.py` — **new**
- `examples/agent_service/main.py` — **modified** (add lifespan wrapper for seeding)
- `examples/agent_service/setup_cs_agents.py` — **modified** (import from `_seed_agents`)

## Verification Results

- ✅ Syntax check: all 3 files pass
- ✅ Unit tests: 4/4 passed (agent count, field validation, import, async signature)
- ✅ Integration tests: 3/3 passed (first seed, idempotent re-seed, name match)
- ✅ E2E smoke test: 5 agents auto-seeded via HTTP API, no regression on existing users
- ✅ No deprecation warnings, no lint errors
