---
skill: project-feature
status: done
date: 2026-08-28
title: Pipeline Refactor — Adopt Framework PipelineProtocol
---

# Change Doc: Pipeline Refactor

## Goal

Refactor the custom pipeline in `examples/` to leverage the framework's
`PipelineProtocol` and `GoalPipeline`, while preserving the existing
sequential pipeline functionality.

## Background

The framework (`src/agentscope/pipeline/`) provides:

- `PipelineProtocol` — a protocol with `reply_stream()` that any pipeline
  must implement. Satisfies the same interface as `Agent`.
- `GoalPipeline` — executor + verifier loop until goal achieved.

The custom pipeline (`examples/agent_service/pipeline_router.py`) provides:

- Sequential multi-step chain (N agents, each with its own instruction)
- Sub-steps within each step
- SSE streaming via custom HTTP endpoints
- Stateless agent assembly

These are **different paradigms** — not a drop-in replacement. The refactor
bridges them.

## Design

### 1. New: `SequentialPipeline` class (`examples/agent_service/sequential_pipeline.py`)

A class implementing `PipelineProtocol` that wraps the existing sequential
chain logic. Instead of inline code in the router, the chain logic lives in
a reusable pipeline class.

```python
class SequentialPipeline:
    """A pipeline that chains agents sequentially.

    Each agent receives its instruction combined with the previous
    agent's output. Implements PipelineProtocol so it can be used
    wherever an Agent is expected.
    """

    def __init__(self, steps, chat_model_config, access, user_id):
        self.steps = steps  # list of PipelineStep
        self.chat_model_config = chat_model_config
        self.access = access
        self.user_id = user_id

    async def reply_stream(self, inputs) -> AsyncGenerator:
        # Yields AgentEvent / Msg for each step
        ...
```

**Rationale**: The existing `_assemble_agent()` and chain logic moves here.
The router becomes thin — it creates a `SequentialPipeline` and either calls
`reply_stream()` directly (for SSE) or collects results (for sync).

### 2. New: Goal pipeline router (`examples/agent_service/goal_pipeline_router.py`)

A new router that exposes the framework's `GoalPipeline` via HTTP:

- `POST /pipeline/goal/run` — synchronous execution
- `POST /pipeline/goal/run/stream` — SSE streaming

Request schema:

```python
class RunGoalPipelineRequest(BaseModel):
    executor_agent_id: str
    verifier_agent_id: str
    instruction: str
    chat_model_config: dict[str, Any]
    max_iters: int = 10
```

The router assembles executor and verifier agents (reusing `_assemble_agent`
from `pipeline_router.py`), creates a `GoalPipeline`, and calls
`reply_stream()`.

### 3. Refactored: `pipeline_router.py`

- Extract `_assemble_agent()` into a shared module (or keep in
  `pipeline_router.py` and import from `goal_pipeline_router.py`)
- The existing `/pipeline/run` and `/pipeline/run/stream` endpoints
  delegate to `SequentialPipeline.reply_stream()`
- SSE event structure stays the same (backward compatible)

### 4. Updated: Frontend

- Add a **pipeline mode selector**: "Sequential" (existing) vs "Goal" (new)
- Sequential mode: unchanged UI
- Goal mode: simpler UI — select executor agent, verifier agent, instruction,
  max iterations
- Results display adapts to the mode:
  - Sequential: per-step results (existing)
  - Goal: executor/verifier iterations with pass/fail status

### 5. API client updates (`pipeline.ts`)

- Add `runGoal()` and `runGoalStream()` methods
- Add `GoalPipelineStreamEvent` type

### 6. Type updates (`types.ts`)

- Add `RunGoalPipelineRequest`, `GoalPipelineStepResult` types

## Impact Assessment

| File | Change |
|------|--------|
| `examples/agent_service/sequential_pipeline.py` | **New** — SequentialPipeline class |
| `examples/agent_service/goal_pipeline_router.py` | **New** — Goal pipeline router |
| `examples/agent_service/pipeline_router.py` | **Modified** — delegate to SequentialPipeline |
| `examples/agent_service/main.py` | **Modified** — register goal_pipeline_router |
| `examples/web_ui/frontend/src/api/pipeline.ts` | **Modified** — add goal pipeline API |
| `examples/web_ui/frontend/src/api/types.ts` | **Modified** — add goal pipeline types |
| `examples/web_ui/frontend/src/pages/pipeline/index.tsx` | **Modified** — add mode selector + goal UI |
| `examples/web_ui/frontend/src/i18n/locales/en.json` | **Modified** — add pipeline mode strings |
| `examples/web_ui/frontend/src/i18n/locales/zh.json` | **Modified** — add pipeline mode strings |
| `examples/EXTENDED_FEATURES.md` | **Modified** — document new pipeline modes |
| `examples/myReadme.md` | **Modified** — update features table |

## Complexity Assessment

| Dimension | Value |
|-----------|-------|
| New/modified files | 11 (2 new, 9 modified) |
| DB/API changes | Yes (new endpoints) |
| Frontend changes | Yes (mode selector, goal UI) |
| Cross-module impact | Backend + Frontend |

**Level: L (Large)** — all 9 phases required.

## Backward Compatibility

- Existing `/pipeline/run` and `/pipeline/run/stream` endpoints keep the
  same request/response schema
- Existing sequential pipeline UI works unchanged when "Sequential" mode
  is selected (default)
- New `/pipeline/goal/run` and `/pipeline/goal/run/stream` are additive
