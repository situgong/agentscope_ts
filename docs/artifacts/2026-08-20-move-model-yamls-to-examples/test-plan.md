---
skill: project-feature
status: in-progress
date: 2026-08-20
short-desc: move-model-yamls-to-examples
---

# Test Plan: Move Custom Model YAMLs to examples/

## Test Matrix

| # | Scenario | Type | Expected Result |
|---|----------|------|-----------------|
| 1 | YAML model loading | Positive | `_load_yaml_models()` returns 5 models |
| 2 | Framework model listing | Positive | `OpenAIChatModel.list_models()` returns 13 models (5 removed) |
| 3 | main.py import | Positive | `import main` succeeds |
| 4 | Framework models correct | Boundary | GLM-5, GLM-4_5V, DeepSeek-V4-Flash, MiniMax-M2, qwen3-vl not in framework list |
| 5 | YAML models correct | Boundary | All 5 models present in YAML loading with correct names/labels |
| 6 | Backend startup | E2E | Server starts without errors |

## E2E Applicability

Backend startup verification. Frontend already has custom model display support.
