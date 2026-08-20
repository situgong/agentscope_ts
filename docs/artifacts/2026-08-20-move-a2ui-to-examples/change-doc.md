---
skill: project-feature
status: in-progress
date: 2026-08-20
short-desc: move-a2ui-to-examples
---

# Change Doc: Move A2UI Tool to examples/

## Goal

Move the `A2UI` tool class out of the framework source (`src/agentscope/`) and into `examples/agent_service/`, where it will be registered as a custom tool via `create_app(extra_agent_tools=...)`. The frontend A2UI components are already in `examples/web_ui/frontend/` and remain unchanged.

## Implementation Plan

### Step 1: Create the A2UI tool in examples/

Create `examples/agent_service/a2ui_tool.py` containing the `A2UI` class, adapted to import from `agentscope` (the installed package) instead of relative imports.

### Step 2: Register A2UI in main.py

Add an `extra_agent_tools` factory to `create_app()` in `examples/agent_service/main.py` that returns `[A2UI()]`.

### Step 3: Remove A2UI from framework source

Remove A2UI from:
- `src/agentscope/tool/_builtin/_a2ui.py` (delete file)
- `src/agentscope/tool/_builtin/__init__.py` (remove import + `__all__` entry)
- `src/agentscope/tool/__init__.py` (remove import + `__all__` entry)
- `src/agentscope/workspace/_base.py` (remove from default tool list)
- `src/agentscope/workspace/_local_workspace.py` (remove from default tool list)

## Impact

- **Framework source**: 5 files modified (A2UI references removed)
- **Examples**: 2 files added/modified (new tool file + main.py registration)
- **Frontend**: No changes needed — already in examples/
- **AGUI middleware**: Stays in framework (separate feature, protocol adapter)

## Complexity: S (Simple)

- 2 new/modified files in examples
- 5 files modified in framework (removal only)
- No DB/API changes
- No frontend changes

## Actual Implementation Results

### Files Added
- `examples/agent_service/a2ui_tool.py` — A2UI tool class, imports from `agentscope` package

### Files Modified (examples)
- `examples/agent_service/main.py` — Added `a2ui_tool_factory` and `extra_agent_tools=a2ui_tool_factory` to `create_app()`

### Files Modified (framework — removal only)
- `src/agentscope/tool/_builtin/__init__.py` — Removed `A2UI` import and `__all__` entry
- `src/agentscope/tool/__init__.py` — Removed `A2UI` import and `__all__` entry
- `src/agentscope/workspace/_base.py` — Removed `A2UI()` from default tool list
- `src/agentscope/workspace/_local_workspace.py` — Removed `A2UI()` from default tool list

### Files Deleted (framework)
- `src/agentscope/tool/_builtin/_a2ui.py` — Deleted

### Verification Results
- Framework imports: OK (A2UI not in exports)
- Example A2UI tool: OK (instantiates correctly)
- main.py import: OK (extra_agent_tools registered)
- AGUI protocol tests: 34/34 passed
- Builtin tool tests: 53 passed, 24 skipped
- Backend startup: OK (server running on port 8000)
- A2UI file deleted: Confirmed
- A2UI not in `agentscope.tool.__all__`: Confirmed
