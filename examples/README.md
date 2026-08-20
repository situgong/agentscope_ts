# AgentScope Examples

This directory contains example applications built on top of the [AgentScope](https://github.com/agentscope-ai/agentscope) framework. Each example demonstrates how to **use and extend** the framework without modifying its source code.

## Core Principle

**We use or extend AgentScope features. We do not modify the framework source code.**

All customizations live in `examples/` only. The framework source (`src/agentscope/`) stays identical to upstream, so you can always pull framework updates without conflicts.

## Examples

### Agent Service (`agent_service/`)

A FastAPI-based, multi-tenant and multi-session agent service built with AgentScope 2.0.

**Features:**

- Multi-agent chat with human-in-the-loop interactions & permission system
- Scheduled tasks and external channel support (Discord, Feishu)
- **Pipeline** — multi-step agent pipeline with per-step instructions, sub-steps, and SSE streaming
- **Custom Models** — add/remove/test custom model names, plus pre-configured model YAMLs (GLM-5, GLM-4.5V, DeepSeek-V4-Flash, MiniMax-M2, Qwen3-VL-30B)
- **A2UI Tool** — agents can emit declarative UI surfaces rendered by the `@a2ui/react` frontend
- Long-term memory via `AgenticMemoryMiddleware`
- Knowledge base with Qdrant vector store

**Quickstart:**

```bash
# Install AgentScope
uv pip install agentscope[full]

# Start Redis (required for storage)
docker run --rm -p 6379:6379 redis:7

# Start the agent service
cd examples/agent_service
python main.py                    # FastAPI on port 8000
```

See [`agent_service/README.md`](agent_service/README.md) for more details.

### Web UI (`web_ui/`)

A React + TypeScript frontend for the agent service, featuring a chat-style interface, pipeline builder, model management, and more.

**Quickstart:**

```bash
cd examples/web_ui
pnpm install
pnpm dev                          # Frontend on 5174, BFF proxy on 5175
```

Then open `http://localhost:5174` and set the API endpoint to `http://localhost:8000`.

### Other Examples

| Directory | Description |
|-----------|-------------|
| `console/` | Terminal-based agent interaction |
| `long_term_memory/` | Memory middleware examples (agentic, mem0, reme) |
| `rag/` | Retrieval-augmented generation examples |
| `workspace/` | Workspace/skill examples |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Web UI (React, port 5174)                           │
│  ├── Chat interface                                  │
│  ├── Pipeline builder                                │
│  ├── Model & credential management                   │
│  └── A2UI surface renderer                           │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│  Agent Service (FastAPI, port 8000)                  │
│  ├── create_app() from agentscope                    │
│  ├── Pipeline router (custom)                        │
│  ├── Custom model router (custom)                    │
│  ├── A2UI tool (extra_agent_tools)                   │
│  └── Long-term memory (extra_agent_middlewares)      │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  AgentScope Framework (src/agentscope/)              │
│  ── unmodified, tracks upstream                      │
└─────────────────────────────────────────────────────┘
```

## Extension Points

The example service demonstrates how to extend AgentScope without modifying the framework:

| Extension Point | How It's Used |
|-----------------|---------------|
| `extra_agent_tools` | Register the A2UI custom tool |
| `extra_agent_middlewares` | Attach long-term memory middleware |
| `custom_subagent_templates` | Define a read-only "explorer" subagent |
| `app.include_router()` | Add pipeline and custom model routers |

## Git Workflow

This repo is a fork of [agentscope-ai/agentscope](https://github.com/agentscope-ai/agentscope). We use a two-branch workflow:

| Branch | Purpose | Rule |
|--------|---------|------|
| `main` | Tracks upstream framework | Never commit directly |
| `my-examples` | All custom work | Only modify files under `examples/` |

```bash
# Work on customizations
git checkout my-examples
# ... edit files in examples/ ...
git commit -m "feat(pipeline): add new step type"

# Sync upstream framework updates
git checkout main
git fetch upstream
git merge upstream/main
git push origin main

# Merge updates into your examples branch
git checkout my-examples
git merge main
git push origin my-examples
```

See [`CLAUDE.md`](CLAUDE.md) for detailed AI assistant guidance.
