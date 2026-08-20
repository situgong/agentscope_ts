# Pipeline Sub-steps Feature — Execute Log

**Date**: 2026-08-20
**Feature**: Add sub-steps to each step in the Pipeline page
**Status**: ✅ Completed

## Summary

Added hierarchical sub-steps to the Pipeline feature. Each pipeline step can now contain
multiple sub-steps, each with its own agent selector and instruction. Sub-steps execute
sequentially after the parent step, with each sub-step receiving the previous output.

## Changes

### 1. Frontend Types (`src/api/types.ts`)
- Added `PipelineSubStep` interface (`agent_id` + `instruction`)
- Extended `PipelineStep` with optional `sub_steps?: PipelineSubStep[]`
- Extended `PipelineStepResult` with optional `sub_results?: PipelineStepResult[]`

### 2. Backend Router (`examples/agent_service/pipeline_router.py`)
- Added `PipelineSubStep` Pydantic model
- Extended `PipelineStep` with `sub_steps: list[PipelineSubStep]` field
- Extended `PipelineStepResult` with `sub_results: list["PipelineStepResult"]` field
- Added `PipelineStepResult.model_rebuild()` to resolve forward reference
- Updated `run_pipeline` endpoint to execute sub-steps after each parent step
- Execution logic: parent step → sub-step 1 → sub-step 2 → ... → next parent step
- The last sub-step's output (or parent's if no sub-steps) feeds into the next parent step

### 3. Frontend Page (`src/pages/pipeline/index.tsx`)
- Added `ChevronRight`/`ChevronDown` icons for collapse/expand
- Added `expandedSteps` state (Set<number>) to track expanded step indices
- Added `toggleStepExpanded`, `addSubStep`, `removeSubStep`, `updateSubStep` functions
- Updated step rendering to include:
  - "Sub-steps" toggle button (shows count when sub-steps exist)
  - "Add sub-step" button
  - Collapsible sub-step list with border-left indentation
  - Each sub-step: numbered "1.1", "1.2", etc., agent selector, instruction textarea, delete button
- Updated `handleRun` to include sub_steps in the API request
- Updated results section to display sub-step results with "Sub-step 1.1: AgentName" labels

### 4. i18n Translations
- Added `pipelinePage` section to `en.json` and `zh.json` with all pipeline-related strings

## Execution Flow

```
Step 1 (agent A, instruction I1)
  → Sub-step 1.1 (agent B, instruction I1.1) — receives Step 1 output
  → Sub-step 1.2 (agent C, instruction I1.2) — receives Sub-step 1.1 output
Step 2 (agent D, instruction I2) — receives Sub-step 1.2 output
  → (no sub-steps)
Step 3 ...
```

## Verification

- ✅ TypeScript compiles with zero errors
- ✅ Python backend starts without errors
- ✅ UI renders sub-step buttons on each step
- ✅ Adding sub-steps works (auto-expands, shows "1 sub-step", "2 sub-steps")
- ✅ Collapsing/expanding sub-steps works
- ✅ Deleting sub-steps works
- ✅ Sub-step numbering correct (1.1, 1.2, etc.)
