# Agent Service

Agent service is a FastAPI-based, multi-tenant and multi-session service built with AgentScope 2.0.

This example demonstrates

- how to set up the agent service with Redis storage, and
- how to launch the service and its companion Web UI

Details about the agent service please refer to the [tutorial](https://docs.agentscope.io/latest/en/deploy/agent-service).

## Prerequisites

- Python ≥ 3.11
- Node.js ≥ 20 with `npx`
- [optional] Gaode/AMap API key in `AMAP_API_KEY` (for the `amap` MCP)

## Quickstart

Install AgentScope from PyPI or source:

```bash
uv pip install agentscope[full]
# or
# uv pip install -e [full]
```

Install Redis and start it as backend storage:

```bash
# macOS (Homebrew)
brew install redis
brew services start redis

# Linux (systemd)
sudo apt install redis-server
sudo systemctl start redis-server

# Docker (cross-platform)
docker run --rm -p 6379:6379 redis:7
```

Start the agent service:

```bash
cd examples/agent_service

python main.py
```

Launch the Web UI in a separate terminal to experience a chat-style interface:

```bash
cd examples/web_ui/

pnpm install
# or npm install

# Run in dev mode
pnpm dev
```

After that, you can set the API endpoint `http://localhost:8000` in the Web UI and start experiencing the agent service.

<img src="https://gw.alicdn.com/imgextra/i2/O1CN01Phmg1G1brIVC8WXyU_!!6000000003518-2-tps-2938-1736.png" alt="Web UI Screenshot" width="100%">

## What Next

- You can customize the service in `main.py` by adding your own MCPs, middlewares, or workspace manager implementations.

- Experience the agent service, including
    - human-in-the-loop interactions & permission system
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01vGGiBw20agWwpzmjy_!!6000000006866-2-tps-2934-1732.png" alt="Permission System" width="100%">

    - schedule tasks
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01Xi3Qw71E2haKKu4z0_!!6000000000294-2-tps-2932-1738.png" alt="Schedule Tasks" width="100%">

    - and more! (stay tuned for future updates)

## Custom Extensions

This example also demonstrates several custom extensions built **on top of** the framework — no `src/agentscope/` files are modified.

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

### A2UI Tool (`a2ui_tool.py`)

A custom tool registered via `create_app(extra_agent_tools=...)` that lets agents emit declarative UI surfaces rendered by the `@a2ui/react` frontend. The tool encodes A2UI v0.9.1 messages as base64 JSONL in `DataBlock` format.

### How Extensions Are Wired

All custom extensions are registered in `main.py`:

```python
app = create_app(
    # ... standard config ...
    extra_agent_tools=a2ui_tool_factory,        # A2UI tool
    extra_agent_middlewares=longterm_memory_factory,  # Long-term memory
)

# Custom routers added after create_app()
app.include_router(pipeline_router)
app.include_router(custom_model_router)
```