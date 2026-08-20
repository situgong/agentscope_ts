---
skill: project-feature
status: review-ready
date: 2026-08-20
short-desc: move-model-yamls-to-examples
---

# Execute Log: Move Custom Model YAMLs to examples/

## Summary

Moved 5 model YAML files (GLM-5, GLM-4_5V, DeepSeek-V4-Flash, MiniMax-M2, qwen3-vl-30b-a3b-instruct) from the framework source (`src/agentscope/model/_openai_chat/_models/`) to `examples/agent_service/models/`. Added a `_load_yaml_models()` function to `custom_model_router.py` that reads these YAML files and merges them into the custom model list endpoint.

## Plan vs Actual

| Aspect | Plan | Actual |
|--------|------|--------|
| YAML files moved | 5 | 5 ✅ |
| Modified example files | 1 (custom_model_router.py) | 1 ✅ |
| Framework files modified | 0 (only deletions) | 0 ✅ |
| Frontend changes | None | None ✅ |
| Complexity | S | S ✅ |

## Key Decisions

1. **Merge YAML models into custom model router**: Rather than wiring `custom_yaml_dir` through the framework's app layer (which would require framework changes), the YAML files are loaded by the example's `custom_model_router.py` and merged with user-added custom models in the `list_custom_models` endpoint.
2. **Deduplication**: User-added custom models take precedence over YAML models with the same name — YAML models are only added if no user-added model with that name exists.
3. **Lazy YAML loading**: The `_load_yaml_models()` function reads from disk on each call, so adding/removing YAML files takes effect without restart.

## Impact

- **Framework source**: 5 YAML files removed from `src/agentscope/model/_openai_chat/_models/`
- **Examples**: 5 YAML files added to `examples/agent_service/models/`, `custom_model_router.py` enhanced with YAML loading
- **Frontend**: No changes (already has custom model display support)
- **Framework model listing**: 13 built-in models remain (gpt-4o, gpt-4.1, o3, etc.)

## Verification Results

| Check | Result |
|-------|--------|
| YAML model loading (5 models) | ✅ Pass |
| Framework model listing (13 models) | ✅ Pass |
| main.py import | ✅ Pass |
| Backend startup | ✅ Server running on port 8000 |

## Phase Tracking

| Phase | Status | Date |
|-------|--------|------|
| Phase 1: UNDERSTAND | ✅ Completed | 2026-08-20 |
| Phase 2: LOCATE & READ SOURCE | ✅ Completed | 2026-08-20 |
| Phase 3: DESIGN | ✅ Completed | 2026-08-20 |
| Phase 4: IMPLEMENT | ✅ Completed | 2026-08-20 |
| Phase 5: TEST | ✅ Completed | 2026-08-20 |
| Phase 6: TEST PLAN | ✅ Completed | 2026-08-20 |
| Phase 7: VERIFY | ✅ Completed | 2026-08-20 |
| Phase 8: DOCUMENT | ✅ Completed | 2026-08-20 |
| Phase 9: EXECUTE LOG | ✅ Completed | 2026-08-20 |

## Unfinished Items

None.
