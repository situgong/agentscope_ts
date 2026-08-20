---
skill: project-feature
status: review-ready
date: 2026-08-20
short-desc: move-a2ui-to-examples
---

# Execute Log: Move A2UI Tool to examples/

## Summary

Moved the `A2UI` tool class from the framework source (`src/agentscope/tool/_builtin/_a2ui.py`) into `examples/agent_service/a2ui_tool.py`, where it is registered as a custom tool via `create_app(extra_agent_tools=...)`. The frontend A2UI components were already in `examples/web_ui/frontend/` and required no changes.

## Plan vs Actual

| Aspect | Plan | Actual |
|--------|------|--------|
| New files | 1 (`a2ui_tool.py`) | 1 ✅ |
| Modified example files | 1 (`main.py`) | 1 ✅ |
| Modified framework files | 5 (removal) | 5 ✅ |
| Deleted framework files | 1 (`_a2ui.py`) | 1 ✅ |
| Frontend changes | None | None ✅ |
| Complexity | S | S ✅ |

## Key Decisions

1. **Use `extra_agent_tools` factory**: The framework's `create_app()` already provides an `extra_agent_tools` parameter — an async factory `(user_id, agent_id, session_id) -> list[ToolBase]`. This is the idiomatic way to register custom tools without modifying framework source.
2. **Keep AGUI middleware in framework**: The AGUI protocol middleware (`src/agentscope/app/middleware/_protocol/_agui.py`) is a protocol adapter, not a tool. It stays in the framework.
3. **Lazy import in factory**: The `a2ui_tool_factory` imports `A2UI` at call time (`from a2ui_tool import A2UI`), following the lazy-loading convention.

## Impact

- **Framework source**: A2UI tool removed from 5 files, source file deleted
- **Examples**: A2UI tool added as custom tool, registered via `extra_agent_tools`
- **Frontend**: No changes (components already in examples)
- **Tests**: All 34 AGUI protocol tests pass, all 53 builtin tool tests pass

## Verification Results

| Check | Result |
|-------|--------|
| Framework imports without A2UI | ✅ Pass |
| Workspace imports without A2UI | ✅ Pass |
| Example A2UI tool imports | ✅ Pass |
| A2UI tool instantiation | ✅ Pass |
| main.py imports | ✅ Pass |
| AGUI protocol tests (34) | ✅ All pass |
| Builtin tool tests (53) | ✅ All pass |
| Backend startup | ✅ Server running on port 8000 |
| A2UI not in `__all__` | ✅ Confirmed |
| A2UI file deleted | ✅ Confirmed |

## Phase Tracking

| Phase | Status | Date |
|-------|--------|------|
| Phase 1: UNDERSTAND | ✅ Completed | 2026-08-20 |
| Phase 2: LOCATE & READ SOURCE | ✅ Completed | 2026-08-20 |
| Phase 3: DESIGN | ✅ Completed | 2026-08-20 |
| Phase 4: Implement | ✅ Completed | 2026-08-20 |
| Phase 5: TEST | ✅ Completed | 2026-08-20 |
| Phase 6: TEST PLAN | ✅ Completed | 2026-08-20 |
| Phase 7: VERIFY | ✅ Completed | 2026-08-20 |
| Phase 8: DOCUMENT | ✅ Completed | 2026-08-20 |
| Phase 9: EXECUTE LOG | ✅ Completed | 2026-08-20 |

## Unfinished Items

None.
