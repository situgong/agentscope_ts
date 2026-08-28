# Extended Features

This document lists all custom extensions built **on top of** the AgentScope framework — no `src/agentscope/` files are modified.

---

## Pipeline (`pipeline_router.py`)

A multi-step agent pipeline where each step has its own agent and instruction. Steps can have sub-steps that run sequentially, after which the parent step re-runs with the combined sub-step outputs to produce a consolidated result.

- `POST /pipeline/run` — synchronous execution
- `POST /pipeline/run/stream` — SSE streaming with progressive results
- SSE events: `step_start`, `step_done`, `sub_step_done`, `step_final`, `pipeline_done`, `error`

## Custom Model Management (`custom_model_router.py`)

Add, remove, and connection-test custom model names under a given credential. Pre-configured model YAMLs (GLM-5, GLM-4.5V, DeepSeek-V4-Flash, MiniMax-M2, Qwen3-VL-30B) are loaded from the `models/` directory and merged with user-added models.

- `GET /custom-model/{credential_id}` — list all custom models
- `POST /custom-model/{credential_id}` — add a custom model
- `DELETE /custom-model/{credential_id}/{model_name}` — remove a custom model
- `POST /custom-model/{credential_id}/test` — test model connection

## Custom Credential Management (`custom_credential_router.py`)

Create, list, and delete custom credentials with a user-defined name, API base URL, and API key. Credentials are stored in `custom_credentials.json` and merged with framework-managed credentials at runtime.

- `GET /custom-credential/` — list all custom credentials
- `POST /custom-credential/` — create a custom credential
- `DELETE /custom-credential/{credential_id}` — delete a custom credential

## A2UI Tool (`a2ui_tool.py`)

A custom tool registered via `create_app(extra_agent_tools=...)` that lets agents emit declarative UI surfaces rendered by the `@a2ui/react` frontend. The tool encodes A2UI v0.9.1 messages as base64 JSONL in `DataBlock` format.

## Robust Agent — Stuck HITL Recovery (`custom_agent.py`)

A custom `Agent` subclass (`RobustAgent`) registered via `create_app(custom_agent_cls=...)`. It gracefully handles sessions that are "stuck" on pending Human-In-The-Loop (HITL) tool calls.

**Problem**: When a previous reply made a tool call requiring user confirmation (ASKING state) and the user sends a **new regular message** instead of a confirmation event, the base `Agent._check_incoming_event` raises `ValueError`. This error is misclassified as a `SETUP` error, showing the user a misleading "check the agent's model, tools and knowledge bases" message. The session becomes permanently stuck in Redis.

**Fix**: `RobustAgent` overrides `_reply_impl` to detect this situation — if the incoming input is a regular message and the agent has pending `ASKING`/`SUBMITTED` tool calls, it calls the framework's existing `_close_unfinished_tool_calls()` method to mark them as interrupted, then proceeds with a fresh reply. No framework source files are modified.

---

## How Extensions Are Wired

All custom extensions are registered in `main.py`:

```python
from custom_agent import RobustAgent

app = create_app(
    # ... standard config ...
    custom_agent_cls=RobustAgent,                     # Stuck HITL recovery
    extra_agent_tools=a2ui_tool_factory,              # A2UI tool
    extra_agent_middlewares=longterm_memory_factory,  # Long-term memory
)

# Custom routers added after create_app()
app.include_router(pipeline_router)
app.include_router(custom_model_router)
app.include_router(custom_credential_router)
```
