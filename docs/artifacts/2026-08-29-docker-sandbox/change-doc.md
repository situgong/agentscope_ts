---
skill: project-feature
status: completed
date: 2026-08-29
title: Switch workspace backend from LocalWorkspaceManager to DockerWorkspaceManager
---

# Change Design: Docker sandbox for agent workspaces

## Goal

Replace `LocalWorkspaceManager` with `DockerWorkspaceManager` in
`examples/agent_service/main.py` so that all agent file operations
(Bash, Read, Write, Edit, etc.) execute inside isolated Docker
containers with persistent host-mounted workdirs.

## Background

The branch `feat/docker-sandbox` was created for this feature, but
the code still uses `LocalWorkspaceManager` — agents run directly on
the WSL filesystem with no isolation. The framework already ships a
fully implemented `DockerWorkspaceManager` with TTL caching, image
build caching, and a background sweeper. The change is a configuration
switch, not new code.

## Implementation Plan

### Modify: `examples/agent_service/main.py`

**Single change**: swap `LocalWorkspaceManager` → `DockerWorkspaceManager`
in the `create_app()` call.

Before:
```python
from agentscope.app.workspace_manager import LocalWorkspaceManager

workspace_manager=LocalWorkspaceManager(
    basedir=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "workspaces",
    ),
    default_mcps=default_mcps,
    skill_paths=[...],
),
```

After:
```python
from agentscope.app.workspace_manager import DockerWorkspaceManager

workspace_manager=DockerWorkspaceManager(
    basedir=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "workspaces",
    ),
    default_mcps=default_mcps,
    skill_paths=[...],
    # base_image defaults to "python:3.11-slim"
    # node_version defaults to "20"
    # isolation defaults to PER_AGENT (same agent's sessions share a workspace)
    # ttl defaults to 3600s (idle containers are torn down after 1 hour)
),
```

### Key behaviors

| Aspect | Behavior |
|--------|----------|
| **Base image** | `python:3.11-slim` (framework default) |
| **Persistence** | `basedir/workspaces/<workspace_id>` bind-mounted to `/workspace` in container — survives container restarts |
| **Isolation** | `PER_AGENT` — same agent's sessions share a workspace (deterministic) |
| **Image caching** | Content-hashed Dockerfile; rebuild skipped on cache hit |
| **TTL** | 3600s — idle containers torn down after 1 hour, workdir persists |
| **Sweeper** | Background task every 300s evicts idle containers |
| **Gateway** | In-container MCP gateway on port 5600 (random host port) |

### No other files need to change

- `DockerWorkspaceManager` has the same public interface as
  `LocalWorkspaceManager` (both extend `WorkspaceManagerBase`)
- `ChatService` and all routers are agnostic to the workspace backend
- Frontend is unaffected — workspace operations are server-side

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Manager | `DockerWorkspaceManager` | Framework built-in, fully implemented |
| Base image | Default `python:3.11-slim` | User requested default |
| Persistence | `host_workdir` via `basedir` | User requested data persistence |
| Isolation | `PER_AGENT` (default) | Same agent's sessions share workspace — persistence-friendly |
| Node.js | Default `"20"` | Matches the host Node version |
| Extra pip | None | Keep image minimal; agents install on demand |

## Complexity Assessment

| Dimension | Value |
|-----------|-------|
| New/modified files | 1 |
| DB/API changes | No |
| Frontend | No |
| Cross-module | No |

**Complexity: S (Simple)**

Per the skill rules, S complexity runs Phase 1-5 + Phase 8 + Phase 9,
skipping Phase 6 and Phase 7. However, since Docker container startup
needs verification, we will run Phase 7 (VERIFY) as well.

## Impact Summary

- `examples/agent_service/main.py` — **modified** (1 import + 1 constructor call)

## Verification Results (Phase 7)

| Check | Result |
|-------|--------|
| Server startup | ✅ FastAPI app starts, agents seeded |
| Docker image build | ✅ `agentscope-workspace:e69eaf6c68a6` (956MB) |
| Container spawn | ✅ `as_ws_8ad6f6e7cb18473d8792136cc0b10b82` running |
| Bind-mount persistence | ✅ Host `workspaces/<id>` → Container `/workspace` |
| Workspace init | ✅ `data/`, `sessions/`, `skills/` dirs created |
| Chat session | ✅ Session created, message sent, agent responded |
| Container working dir | ✅ `/workspace` |

### Container details

- **Image**: `agentscope-workspace:e69eaf6c68a6` (content-hashed tag)
- **Container name**: `as_ws_<workspace_id>` (stable across restarts)
- **Bind-mount**: `<basedir>/<workspace_id>` → `/workspace`
- **Base image**: `python:3.11-slim` + `node:20-slim` + `uv` + `ripgrep`
- **TTL**: 3600s (idle containers torn down after 1 hour, workdir persists)
- **Sweeper**: Background task every 300s
