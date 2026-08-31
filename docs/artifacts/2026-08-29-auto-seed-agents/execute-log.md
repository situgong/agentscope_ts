---
skill: project-feature
status: review-ready
date: 2026-08-29
title: Auto-seed inner agents on backend startup
---

# Execute Log: Auto-seed inner agents on backend startup

## Summary

Replaced the manual `setup_cs_agents.py` script with automatic agent
creation at backend startup. The "Customer Service Agent" and its 4
pipeline sub-agents are now seeded into Redis on the first server
start, with no extra steps required.

## Phase Tracking

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 1 | UNDERSTAND | ✅ Completed | Requirement: auto-create agents on startup, no manual script |
| 2 | LOCATE & READ SOURCE | ✅ Completed | Read main.py, setup_cs_agents.py, cs_pipeline_agent.py, _lifespan.py, storage layer |
| 3 | DESIGN | ✅ Completed | Complexity: S. New file `_seed_agents.py`, modify `main.py` + `setup_cs_agents.py` |
| 4 | IMPLEMENT | ✅ Completed | 3 files changed. Fixed: logger import path, AgentData requires ContextConfig+ReActConfig, lifespan ordering |
| 5 | TEST | ✅ Completed | 7 tests passed (4 unit + 3 integration) |
| 6 | TEST PLAN | ✅ Completed | 9 scenarios defined (4 positive, 2 boundary, 1 exception, 1 regression, 1 E2E) |
| 7 | VERIFY | ✅ Completed | E2E smoke test: 5 agents auto-seeded, no regression, idempotent |
| 8 | DOCUMENT | ✅ Completed | change-doc.md + test-plan.md updated |
| 9 | EXECUTE LOG | ✅ Completed | This document |

## Plan vs. Actual

| Aspect | Plan | Actual |
|--------|------|--------|
| Files changed | 3 (1 new + 2 modified) | 3 (exactly as planned) |
| Complexity | S (Simple) | S (confirmed) |
| Startup hook | `@app.on_event("startup")` | Lifespan wrapper (avoided deprecation warning) |
| AgentData construction | Just name + system_prompt | Needed ContextConfig() + ReActConfig() defaults |
| Lifespan ordering | Seed before original lifespan | Seed **after** original lifespan enters (storage must be initialized first) |

## Key Decisions

1. **Lifespan wrapper over `on_event`**: FastAPI deprecates `@app.on_event("startup")`. Used `asynccontextmanager` to wrap the existing lifespan, running seeding after storage/resources are entered.

2. **Storage layer over HTTP API**: Seeding calls `storage.upsert_agent()` directly instead of HTTP API calls. This works before the server is listening and is faster.

3. **Env var for user ID**: `INNER_AGENT_USER_ID` env var (default `"inner"`) keeps built-in agents separate from real users. Deployments can customize.

4. **Single source of truth**: `INNER_AGENTS` in `_seed_agents.py` is the canonical definition. `setup_cs_agents.py` imports from it, eliminating prompt duplication.

## Impact

- **New file**: `examples/agent_service/_seed_agents.py` — 5 agent definitions + `seed_inner_agents()` function
- **Modified**: `examples/agent_service/main.py` — lifespan wrapper for auto-seeding
- **Modified**: `examples/agent_service/setup_cs_agents.py` — imports `INNER_AGENTS` from `_seed_agents`

## Verification Results

- ✅ All 5 agents auto-created on startup
- ✅ Idempotent: restart creates no duplicates
- ✅ No regression: existing user agents unaffected
- ✅ No deprecation warnings, no lint errors

## Unfinished Items

None. All planned work is complete.
