---
skill: project-feature
phase: execute-log
date: 2026-08-29
title: Docker sandbox refactor — execution log
---

# Execute Log: Docker sandbox for agent workspaces

## Summary

Switched the workspace backend in `examples/agent_service/main.py` from
`LocalWorkspaceManager` to `DockerWorkspaceManager`, enabling Docker-based
sandboxing for all agent file operations with persistent host-mounted
workdirs.

## Changes Made

### `examples/agent_service/main.py`

- **Line 36**: Import changed from `LocalWorkspaceManager` to `DockerWorkspaceManager`
- **Line 112**: Constructor call changed from `LocalWorkspaceManager(...)` to `DockerWorkspaceManager(...)`
- Parameters kept identical: `basedir`, `default_mcps`, `skill_paths`
- Docker-specific parameters use framework defaults: `base_image="python:3.11-slim"`, `node_version="20"`, `isolation=PER_AGENT`, `ttl=3600`

## Execution Steps

| Step | Action | Result |
|------|--------|--------|
| 1 | Read `DockerWorkspaceManager` source | API compatible with `LocalWorkspaceManager` |
| 2 | Verified `aiodocker` 0.27.0 installed | ✅ |
| 3 | Verified Docker Engine 29.7.2 running | ✅ |
| 4 | Modified `main.py` (import + constructor) | ✅ No errors |
| 5 | Syntax check (AST parse) | ✅ |
| 6 | Import check (`DockerWorkspaceManager`) | ✅ |
| 7 | Constructor signature check | ✅ All params accepted |
| 8 | Started backend on port 50022 | ✅ Server running, 5 agents seeded |
| 9 | Created chat session | ✅ Session `2dc949cb514a4874910cbafa09c78e91` |
| 10 | Sent chat message | ✅ Triggered Docker workspace init |
| 11 | Docker image build | ✅ `agentscope-workspace:e69eaf6c68a6` (956MB, ~4min) |
| 12 | Container started | ✅ `as_ws_8ad6f6e7cb18473d8792136cc0b10b82` |
| 13 | Bind-mount verified | ✅ Host `workspaces/<id>` → Container `/workspace` |
| 14 | Chat completed | ✅ Session status `idle` |
| 15 | Cleaned up test resources | ✅ Server stopped, container removed |

## Verification Evidence

- Docker image: `agentscope-workspace:e69eaf6c68a6` (956MB)
- Container: `as_ws_8ad6f6e7cb18473d8792136cc0b10b82`
- Bind-mount: `/home/gongsitu/project/agentscope/examples/agent_service/workspaces/8ad6f6e7cb18473d8792136cc0b10b82` → `/workspace`
- Workspace dirs: `data/`, `sessions/`, `skills/`

## Complexity

- **Assessed**: S (Simple) — 1 file modified, no DB/API/frontend changes
- **Phases executed**: 1, 2, 3, 4, 5, 7, 8, 9 (Phase 6 skipped per S rules)

## Status

✅ **Complete** — Docker sandbox is fully functional.
