---
skill: project-feature
status: in-progress
date: 2026-08-20
short-desc: move-a2ui-to-examples
---

# Test Plan: Move A2UI Tool to examples/

## Test Matrix

| # | Scenario | Type | Expected Result |
|---|----------|------|-----------------|
| 1 | Framework imports without A2UI | Positive | `from agentscope.tool import Bash, Edit, ...` succeeds; `A2UI` not in `agentscope.tool` |
| 2 | Workspace imports without A2UI | Positive | `from agentscope.workspace._base import WorkspaceBase` succeeds |
| 3 | Example A2UI tool imports | Positive | `from a2ui_tool import A2UI` succeeds from `examples/agent_service/` |
| 4 | A2UI tool instantiation | Positive | `A2UI()` creates tool with `name="A2UI"`, `is_read_only=True` |
| 5 | main.py imports | Positive | `import main` succeeds with `extra_agent_tools=a2ui_tool_factory` |
| 6 | AGUI protocol tests | Regression | All 34 tests pass (AGUI middleware is separate from A2UI tool) |
| 7 | Builtin tool tests | Regression | All builtin tool tests pass (Bash, Read, Write, Edit, Glob, Grep) |
| 8 | A2UI not in framework `__all__` | Boundary | `A2UI` not in `agentscope.tool.__all__` |
| 9 | A2UI file deleted from framework | Boundary | `src/agentscope/tool/_builtin/_a2ui.py` does not exist |
| 10 | Backend starts and serves | E2E | `python main.py` starts without import errors |

## E2E Applicability

Full E2E with backend startup verification. Frontend A2UI rendering is unchanged (components already in `examples/web_ui/frontend/`).
