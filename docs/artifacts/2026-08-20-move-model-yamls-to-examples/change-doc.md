---
skill: project-feature
status: in-progress
date: 2026-08-20
short-desc: move-model-yamls-to-examples
---

# Change Doc: Move Custom Model YAMLs to examples/

## Goal

Move 5 model YAML files from the framework source (`src/agentscope/model/_openai_chat/_models/`) into `examples/agent_service/models/`, and load them via the custom model router so they appear in the frontend's model list without modifying framework source.

## Files to Move

1. `GLM-5.yaml`
2. `GLM-4_5V.yaml`
3. `DeepSeek-V4-Flash.yaml`
4. `MiniMax-M2.yaml`
5. `qwen3-vl-30b-a3b-instruct.yaml`

## Implementation Plan

### Step 1: Move YAML files

Move the 5 YAML files from `src/agentscope/model/_openai_chat/_models/` to `examples/agent_service/models/`.

### Step 2: Add YAML loading to custom_model_router.py

Add a `_load_yaml_models()` function that reads all `.yaml` files from the `models/` directory and returns them as `CustomModelInfo` dicts. Merge these with the JSON-stored custom models in the `list_custom_models` endpoint so they appear alongside user-added custom models.

### Step 3: Verify

- Framework `list_models()` still works for remaining built-in models (gpt-4o, etc.)
- The 5 moved models appear in the custom model list
- No framework source modifications beyond YAML file deletion

## Complexity: S (Simple)

- 5 YAML files moved (delete from framework, add to examples)
- 1 file modified in examples (custom_model_router.py)
- No DB/API changes
- No frontend changes

## Actual Implementation Results

### Files Moved
- `src/agentscope/model/_openai_chat/_models/GLM-5.yaml` → `examples/agent_service/models/GLM-5.yaml`
- `src/agentscope/model/_openai_chat/_models/GLM-4_5V.yaml` → `examples/agent_service/models/GLM-4_5V.yaml`
- `src/agentscope/model/_openai_chat/_models/DeepSeek-V4-Flash.yaml` → `examples/agent_service/models/DeepSeek-V4-Flash.yaml`
- `src/agentscope/model/_openai_chat/_models/MiniMax-M2.yaml` → `examples/agent_service/models/MiniMax-M2.yaml`
- `src/agentscope/model/_openai_chat/_models/qwen3-vl-30b-a3b-instruct.yaml` → `examples/agent_service/models/qwen3-vl-30b-a3b-instruct.yaml`

### Files Modified (examples)
- `examples/agent_service/custom_model_router.py` — Added `yaml` import, `_YAML_MODELS_DIR` path, `_load_yaml_models()` function, and merged YAML models into `list_custom_models` endpoint

### Verification Results
- YAML model loading: 5/5 models loaded correctly
- Framework model listing: 13 built-in models remain (5 removed)
- main.py import: OK
- Backend startup: OK (server running on port 8000)
