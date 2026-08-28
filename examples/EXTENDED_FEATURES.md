# Extended Features

This document lists all custom extensions built **on top of** the AgentScope framework — no `src/agentscope/` files are modified.

---

## Agent Service (`agent_service/`)

### Pipeline (`pipeline_router.py`)

A multi-step agent pipeline where each step has its own agent and instruction. Steps can have sub-steps that run sequentially, after which the parent step re-runs with the combined sub-step outputs to produce a consolidated result.

- `POST /pipeline/run` — synchronous execution
- `POST /pipeline/run/stream` — SSE streaming with progressive results
- SSE events: `step_start`, `step_done`, `sub_step_done`, `step_final`, `pipeline_done`, `error`

### Custom Model Management (`custom_model_router.py`)

Add, remove, and connection-test custom model names under a given credential. Pre-configured model YAMLs (GLM-5, GLM-4.5V, DeepSeek-V4-Flash, MiniMax-M2, Qwen3-VL-30B) are loaded from the `models/` directory and merged with user-added models.

- `GET /custom-model/{credential_id}` — list all custom models
- `POST /custom-model/{credential_id}` — add a custom model
- `DELETE /custom-model/{credential_id}/{model_name}` — remove a custom model
- `POST /custom-model/{credential_id}/test` — test model connection

### Custom Credential Management (`custom_credential_router.py`)

Create, list, and delete custom credentials with a user-defined name, API base URL, and API key. Credentials are stored in `custom_credentials.json` and merged with framework-managed credentials at runtime.

- `GET /custom-credential/` — list all custom credentials
- `POST /custom-credential/` — create a custom credential
- `DELETE /custom-credential/{credential_id}` — delete a custom credential

### A2UI Tool (`a2ui_tool.py`)

A custom tool registered via `create_app(extra_agent_tools=...)` that lets agents emit declarative UI surfaces rendered by the `@a2ui/react` frontend. The tool encodes A2UI v0.9.1 messages as base64 JSONL in `DataBlock` format.

### Robust Agent — Stuck HITL Recovery (`custom_agent.py`)

A custom `Agent` subclass (`RobustAgent`) registered via `create_app(custom_agent_cls=...)`. It gracefully handles sessions that are "stuck" on pending Human-In-The-Loop (HITL) tool calls.

**Problem**: When a previous reply made a tool call requiring user confirmation (ASKING state) and the user sends a **new regular message** instead of a confirmation event, the base `Agent._check_incoming_event` raises `ValueError`. This error is misclassified as a `SETUP` error, showing the user a misleading "check the agent's model, tools and knowledge bases" message. The session becomes permanently stuck in Redis.

**Fix**: `RobustAgent` overrides `_reply_impl` to detect this situation — if the incoming input is a regular message and the agent has pending `ASKING`/`SUBMITTED` tool calls, it calls the framework's existing `_close_unfinished_tool_calls()` method to mark them as interrupted, then proceeds with a fresh reply. No framework source files are modified.

### Long-Term Memory (`main.py` → `longterm_memory_factory`)

Agentic long-term memory via `AgenticMemoryMiddleware`, attached through `create_app(extra_agent_middlewares=...)`. Memory is stored as Markdown files under the session's workspace, surviving across sessions of the same agent.

### Read-Only Explorer Subagent (`main.py` → `custom_subagent_templates`)

A custom subagent template (`type="explorer"`) with `PermissionMode.EXPLORE` — can read files but cannot modify, create, or delete them. Used for investigation tasks within multi-agent teams.

---

## Web UI (`web_ui/`)

### Pipeline Builder (`frontend/src/pages/pipeline/`)

A visual pipeline builder page where users can:
- Add/remove pipeline steps, each with its own agent and instruction
- Add sub-steps to any step
- Run the pipeline synchronously or with SSE streaming
- View progressive results as each step/sub-step completes

### Custom Credential & Model Management (`frontend/src/pages/credential/`)

An extended credential page that adds:
- **Create Custom Credential** dialog — user-defined name, API base URL, API key, and API type (Chat Completions / Responses / Messages)
- **Custom Model** management — add/remove/test custom model names under a credential, with pre-configured model cards (GLM-5, GLM-4.5V, DeepSeek-V4-Flash, MiniMax-M2, Qwen3-VL-30B)
- Side-by-side display of framework-managed and custom credentials

### A2UI Surface Renderer (`frontend/src/components/a2ui/`)

Renders A2UI v0.9.1 declarative UI surfaces emitted by the agent's A2UI tool. Features:
- Parses base64 JSONL `DataBlock` content from agent messages
- Normalizes `catalogId` (maps `"basic"` to the full URL expected by `@a2ui/react`)
- Collapsible surface panel with expand/collapse toggle
- Integrated into the chat message bubble via `A2UIRenderer`

### Tool Result Renderers (`frontend/src/components/chat/tool-renderers/`)

Custom renderers for built-in tool results displayed in the chat:
- `BashRenderer` — terminal-style output for bash tool
- `EditRenderer` — diff preview for file edits
- `ReadRenderer` — file content viewer
- `WriteRenderer` — file write confirmation
- `GlobRenderer` / `GrepRenderer` — search result listing
- `TaskCreateRenderer` — task creation card
- `A2UIRenderer` — A2UI surface rendering
- `DefaultRenderer` — fallback for unknown tools

### Onboarding Tour (`frontend/src/components/tour/`)

An interactive product tour using `onborda` that guides new users through:
- Creating an agent
- Creating a session
- Selecting an LLM
- Setting permission mode
- Sending a message

### Internationalization (`frontend/src/i18n/`)

Full i18n support with `i18next` and `react-i18next`:
- English (`en.json`) and Chinese (`zh.json`) locales
- Auto-detection of browser language
- All UI text is translation-keyed

### Channel Management (`frontend/src/pages/channel/`)

A channel management page for external messaging platform integration:
- Create/configure/delete channels (Discord, Feishu, DingTalk)
- Enable/disable channels with live status badges
- Bind sessions to specific chat IDs
- Resizable detail panel for channel configuration

### Setup Wizard (`frontend/src/pages/setup/`)

A first-run setup page that:
- Checks backend health endpoint (`/api/health`)
- Prompts for the API endpoint URL
- Validates connectivity before proceeding
- Shows which subsystems are not ready (Redis, etc.)

---

## How Extensions Are Wired

### Agent Service (`agent_service/main.py`)

```python
from custom_agent import RobustAgent

app = create_app(
    # ... standard config ...
    custom_agent_cls=RobustAgent,                     # Stuck HITL recovery
    extra_agent_tools=a2ui_tool_factory,              # A2UI tool
    extra_agent_middlewares=longterm_memory_factory,  # Long-term memory
    custom_subagent_templates=[...],                  # Explorer subagent
)

# Custom routers added after create_app()
app.include_router(pipeline_router)
app.include_router(custom_model_router)
app.include_router(custom_credential_router)
```

### Web UI (`web_ui/frontend/src/App.tsx`)

Custom pages are registered as routes in the React Router:

```tsx
const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/chat/:agentId?/:sessionId?/:memberId?', element: <ChatPage /> },
      { path: '/pipeline', element: <PipelinePage /> },
      { path: '/credential', element: <CredentialPage /> },
      { path: '/channel', element: <ChannelPage /> },
      { path: '/schedule', element: <SchedulePage /> },
      { path: '/knowledge', element: <KnowledgePage /> },
      { path: '/mcp', element: <MCPHubPage /> },
      { path: '/skill', element: <SkillHubPage /> },
      // ...
    ],
  },
]);
```

### Extension Points Used

| Extension Point | Where | What It Does |
|-----------------|-------|--------------|
| `custom_agent_cls` | `create_app()` | `RobustAgent` — stuck HITL recovery |
| `extra_agent_tools` | `create_app()` | A2UI custom tool |
| `extra_agent_middlewares` | `create_app()` | Long-term memory middleware |
| `custom_subagent_templates` | `create_app()` | Read-only "explorer" subagent |
| `app.include_router()` | `main.py` | Pipeline, custom model, custom credential routers |
| React Router routes | `App.tsx` | Pipeline builder, channel management, setup wizard pages |
| Custom components | `components/` | A2UI renderer, tool renderers, onboarding tour |
