# CLAUDE.md — Examples

## Core Principle

**We USE or EXTEND AgentScope features. We do NOT modify the AgentScope source code.**

The framework source lives in `src/agentscope/`. The examples in this directory consume the framework as a dependency — they import from `agentscope`, configure it, and build on top of it. Never edit files under `src/agentscope/` when working on examples.

If a feature is missing from the framework, prefer:
1. Compose existing framework primitives in a new way within the example.
2. Subclass or wrap a framework class within the example code.
3. Open a framework-level issue/PR separately — do not patch the framework from here.

## Directory Structure

```
examples/
├── agent_service/     # FastAPI backend (port 8000) + pipeline router
├── console/           # Terminal-based agent interaction
├── long_term_memory/  # Memory middleware examples (agentic, mem0, reme)
├── rag/               # Retrieval-augmented generation examples
├── web_ui/            # React + TypeScript frontend (port 5174)
│   ├── frontend/      # Vite + React + shadcn/ui
│   └── backend/       # Node.js BFF proxy
└── workspace/         # Workspace/skill examples
```

## Tech Stack

### Backend (agent_service/)
- **Python ≥ 3.11**, FastAPI, uvicorn
- **AgentScope** installed via `uv pip install agentscope[full]` (or `-e [full]` from repo root)
- **Redis** on `localhost:6379` for storage
- **Qdrant** (in-memory) for vector store
- Virtual env: `.venv/` at repo root (`d:\haier\0-joy\26\github\agentscope_ts\.venv\`)
- Python executable: `.venv\Scripts\python.exe`

### Frontend (web_ui/)
- **Node.js ≥ 20**, pnpm, Vite
- **React + TypeScript**, shadcn/ui components
- **i18n**: `en.json` / `zh.json` locale files in `frontend/src/i18n/locales/`
- Dev server: `pnpm dev` (runs frontend on 5174 + backend BFF on 5175)

## Common Commands

```bash
# Backend
cd examples/agent_service
python main.py                          # Start FastAPI on port 8000

# Frontend
cd examples/web_ui
pnpm install                            # Install dependencies
pnpm dev                                # Start dev servers (5174 + 5175)
pnpm build                              # Production build
pnpm format                             # Prettier + ESLint fix
```

## Coding Conventions

### Python (agent_service/)
- Follow the AgentScope code review guide (see `.github/copilot-instructions.md`)
- Docstrings: English, reStructuredText format, full Args/Returns
- Lazy-load third-party imports (not in `pyproject.toml` dependencies) at point of use
- No hardcoded API keys — use environment variables

### TypeScript (web_ui/frontend/)
- Use existing shadcn/ui components from `src/components/ui/`
- API clients go in `src/api/`, types in `src/api/types.ts`
- Pages go in `src/pages/`, shared components in `src/components/`
- Add i18n keys to both `en.json` and `zh.json`
- Use `prettier` for formatting (config in `.prettierrc`)

### SSE Streaming Pattern
- Backend: use `StreamingResponse` with `text/event-stream`, format frames as `data: {json}\n\n`
- Frontend: use `fetch` + `ReadableStream` reader, parse `data: ` lines
- Event types: define union types in the API client file

## Custom Model YAMLs

The `agent_service/models/` directory contains pre-configured model YAML files (GLM-5, GLM-4.5V, DeepSeek-V4-Flash, MiniMax-M2, Qwen3-VL-30B). These are loaded by `_load_yaml_models()` in `custom_model_router.py` and merged with user-added custom models in the `/custom-model/{credential_id}` endpoint.

- **YAML directory**: `examples/agent_service/models/`
- **Loading**: `custom_model_router.py` → `_load_yaml_models()`
- **Endpoint**: `GET /custom-model/{credential_id}` returns YAML models + user-added models

These YAMLs were moved out of the framework source to demonstrate how to extend AgentScope with custom model definitions without modifying `src/agentscope/`.

## A2UI Custom Tool

The `agent_service/a2ui_tool.py` contains the `A2UI` tool — a custom tool that lets agents emit declarative UI surfaces rendered by the `@a2ui/react` frontend. It is registered via `create_app(extra_agent_tools=a2ui_tool_factory)` in `main.py`.

- **Tool file**: `examples/agent_service/a2ui_tool.py`
- **Registration**: `extra_agent_tools` factory in `examples/agent_service/main.py`
- **Frontend renderer**: `examples/web_ui/frontend/src/components/a2ui/A2UISurface.tsx`
- **Tool result renderer**: `examples/web_ui/frontend/src/components/chat/tool-renderers/A2UIRenderer.tsx`

This tool was moved out of the framework source to demonstrate how to extend AgentScope with custom tools without modifying `src/agentscope/`.

## Pipeline Feature

The `agent_service/pipeline_router.py` implements a multi-step agent pipeline:
- Each step has an agent + instruction, optionally with sub-steps
- Execution flow: parent step → sub-steps (sequential) → parent re-runs with sub-step outputs (consolidation) → next step
- Two endpoints: `POST /pipeline/run` (sync) and `POST /pipeline/run/stream` (SSE)
- SSE events: `step_start`, `step_done`, `sub_step_done`, `step_final`, `pipeline_done`, `error`

## Testing

- Manual testing via the web UI at `http://localhost:5174`
- Backend logs appear in the terminal running `python main.py`
- Use the browser DevTools Network tab to inspect SSE streams

## Git Workflow

This repo is a fork of [agentscope-ai/agentscope](https://github.com/agentscope-ai/agentscope). We use a two-branch workflow to keep example customizations independent from framework updates.

### Branch Strategy

| Branch | Purpose | Rule |
|--------|---------|------|
| `main` | Tracks upstream framework | Never commit directly. Only `git pull upstream main` |
| `my-examples` | All custom work | Only modify files under `examples/`. Never touch `src/agentscope/` |

### Remotes

- `origin` → `git@github.com:situgong/agentscope_ts.git` (your fork)
- `upstream` → `https://github.com/agentscope-ai/agentscope.git` (original framework)

### Daily Workflow

```bash
# 1. Work on my-examples — make changes only in examples/
git checkout my-examples
# ... edit files in examples/ ...
git commit -m "feat(pipeline): add new step type"

# 2. When upstream framework updates, sync:
git checkout main
git fetch upstream
git merge upstream/main          # or: git rebase upstream/main
git push origin main             # push synced main to your fork

# 3. Merge upstream updates into your examples branch
git checkout my-examples
git merge main                   # bring framework updates into your branch
# Resolve conflicts if any (should be rare — examples/ and src/ don't overlap)
git push origin my-examples
```

### Key Principle

**All customizations live in `examples/` only.** The framework source (`src/agentscope/`) stays identical to upstream. This means:
- Upstream merges are conflict-free (different directories)
- You can always update the framework without breaking your examples
- Your examples are portable — they work with any version of the framework that has the same extension points

### Git Conventions

- Follow Conventional Commits: `feat(scope): description`, `fix(scope): description`
- Common scopes: `pipeline`, `web_ui`, `agent_service`, `rag`, `memory`
