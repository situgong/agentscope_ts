# Pipeline SSE Streaming — Execute Log

**Date**: 2026-08-20
**Feature**: Stream pipeline output via SSE
**Status**: ✅ Completed

## Summary

Changed the Pipeline run from synchronous (wait for all steps) to SSE streaming.
Each step/sub-step result is pushed to the frontend immediately as it completes,
so the user sees output progressively instead of waiting for the entire pipeline.

## Changes

### 1. Backend (`examples/agent_service/pipeline_router.py`)
- Added `POST /pipeline/run/stream` SSE endpoint
- Uses `StreamingResponse` with `text/event-stream` media type
- Emits events: `step_start`, `step_done`, `sub_step_done`, `pipeline_done`, `error`
- Each event is `data: {json}\n\n` format
- Original `POST /pipeline/run` kept for backward compatibility

### 2. Frontend API (`examples/web_ui/frontend/src/api/pipeline.ts`)
- Added `PipelineStreamEvent` union type for SSE events
- Added `runStream` async generator method using `client.stream()`
- Reuses the existing fetch-based SSE pattern from `session.ts`

### 3. Frontend Page (`examples/web_ui/frontend/src/pages/pipeline/index.tsx`)
- `handleRun` now uses `pipelineApi.runStream()` instead of `pipelineApi.run()`
- Added `streamingStep` state to track which step is currently running
- Results render progressively as events arrive
- Shows spinner on the currently running step
- Results card shows "Running step N…" during execution

## SSE Event Format

```
data: {"type": "step_start", "step_index": 0, "agent_id": "...", "agent_name": "..."}

data: {"type": "step_done", "step_index": 0, "agent_id": "...", "agent_name": "...", "instruction": "...", "reply": {...}}

data: {"type": "sub_step_done", "step_index": 0, "sub_step_index": 0, "agent_id": "...", "agent_name": "...", "instruction": "...", "reply": {...}}

data: {"type": "pipeline_done", "total_steps": 2}
```

## Verification

- ✅ TypeScript compiles with zero errors
- ✅ Python backend starts without errors
- ✅ Both endpoints registered in OpenAPI schema (`/pipeline/run` + `/pipeline/run/stream`)
- ✅ Frontend page loads correctly
