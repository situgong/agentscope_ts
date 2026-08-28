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
# Windows (Memurai):  Install from https://www.memurai.com/get-memurai
#                     Memurai runs as a Windows service on port 6379 by default
#                     CLI:  "D:\Program Files\Memurai\memurai-cli.exe"
#                     Flush: memurai-cli.exe flushdb
# Linux/Mac:          docker run --rm -p 6379:6379 redis:7

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

For the full list of extended features across both the agent service and the web UI, see **[EXTENDED_FEATURES.md](EXTENDED_FEATURES.md)**.

## Development Setup

### Prerequisites

- **Python ≥ 3.11** with [`uv`](https://docs.astral.sh/uv/) package manager
- **Node.js ≥ 20** with `pnpm`
- **Redis** on `localhost:6379`
- **Git** with SSH key configured for GitHub

### First-Time Setup

```bash
# 1. Clone your fork
git clone git@github.com:situgong/agentscope_ts.git
cd agentscope_ts

# 2. Add upstream remote (one-time)
git remote add upstream https://github.com/agentscope-ai/agentscope.git

# 3. Switch to the examples branch
git checkout my-examples

# 4. Create virtual environment and install AgentScope in editable mode
uv venv .venv
# Windows:  .venv\Scripts\activate
# Linux:    source .venv/bin/activate
uv pip install -e "[full]"

# 5. Start Redis
#    Windows:  Install Memurai (https://www.memurai.com/get-memurai)
#              It runs as a Windows service on port 6379 automatically
#              CLI path:  "D:\Program Files\Memurai\memurai-cli.exe"
#              Flush data:  memurai-cli.exe flushdb
#    Linux/Mac:  docker run --rm -p 6379:6379 redis:7

# 6. Start the backend (terminal 1)
cd examples/agent_service
python main.py                    # FastAPI on port 8000

# 7. Start the frontend (terminal 2)
cd examples/web_ui
pnpm install
pnpm dev                          # Vite on 5174 + BFF on 5175
```

Open `http://localhost:5174` and set the API endpoint to `http://localhost:8000`.

### Daily Development

```bash
# Always work on my-examples — never commit to main
git checkout my-examples

# Backend
cd examples/agent_service
python main.py                    # FastAPI on port 8000

# Frontend
cd examples/web_ui
pnpm dev                          # Frontend on 5174 + BFF on 5175
```

## Git Workflow

This repo is a fork of [agentscope-ai/agentscope](https://github.com/agentscope-ai/agentscope). We use a two-branch workflow to keep example customizations independent from framework updates.

### Branch Strategy

| Branch | Purpose | Rule |
|--------|---------|------|
| `main` | Tracks upstream framework | Never commit directly. Only upstream merges |
| `my-examples` | All custom work | Only modify files under `examples/`. Never touch `src/agentscope/` |

### Remotes

- `origin` → `git@github.com:situgong/agentscope_ts.git` (your fork)
- `upstream` → `https://github.com/agentscope-ai/agentscope.git` (original framework)

### Working on Customizations

```bash
git checkout my-examples
# ... edit files in examples/ ...
git commit -m "feat(pipeline): add new step type"
git push origin my-examples
```

### Updating AgentScope from Upstream

When the upstream framework releases updates:

```bash
# 1. Fetch and merge upstream into main
git checkout main
git fetch upstream
git merge upstream/main
git push origin main

# 2. Merge into your examples branch
git checkout my-examples
git merge main
git push origin my-examples

# 3. Reinstall if dependencies changed
uv pip install -e "[full]"

# 4. Restart the backend to load framework changes
cd examples/agent_service
python main.py
```

> **Note:** AgentScope is installed in editable mode (`-e`), which links to `src/agentscope/` in the repo. When you merge upstream changes, the framework code updates immediately — no reinstall needed unless `pyproject.toml` dependencies changed.

### Key Principle

**All customizations live in `examples/` only.** The framework source (`src/agentscope/`) stays identical to upstream. This means:
- Upstream merges are conflict-free (different directories)
- You can always update the framework without breaking your examples
- Your examples are portable — they work with any framework version that has the same extension points

See [`CLAUDE.md`](CLAUDE.md) for detailed AI assistant guidance.
