---
skill: project-feature
status: review-ready
date: 2026-08-20
short-desc: custom-credential-api-type
---

# Execute Log: Custom Credential API Type

## Summary

Replaced the provider-based preset system (ZhipuAI, DeepSeek, MiniMax, Alibaba, Custom) in custom credentials with a simpler API-type-based system (`chat_completions`, `responses`, `messages`). The API type determines the request/response format for models in a credential group. All 5 YAML model files updated from `provider: <vendor>` to `api_type: chat_completions`.

## Plan vs Actual

| Aspect | Plan | Actual |
|--------|------|--------|
| Modified backend files | 2 (`custom_credential_router.py`, `custom_model_router.py`) | 2 ✅ |
| Modified frontend files | 3 (`CreateCustomCredentialDialog.tsx`, `types.ts`, `en.json` + `zh.json`) | 4 ✅ |
| Modified YAML files | 5 | 5 ✅ |
| New files | 0 | 0 ✅ |
| Complexity | S | S ✅ |

## Key Decisions

1. **Three API types only**: `chat_completions` (OpenAI Chat Completions), `responses` (OpenAI Responses API), `messages` (Anthropic Messages API). These directly map to the three formatter families in AgentScope.
2. **Default to `chat_completions`**: Most custom endpoints use OpenAI-compatible format, so this is the sensible default.
3. **No auto-fill of base URL**: The original provider presets auto-filled the base URL (e.g. ZhipuAI → `https://open.bigmodel.cn/...`). Removed this since the user always provides their own base URL for custom credentials.
4. **Field rename, not structural change**: `provider` → `api_type` is a 1:1 field replacement. No new tables, no new endpoints, no new storage logic.

## Files Changed

### Backend

| File | Change |
|------|--------|
| `examples/agent_service/custom_credential_router.py` | `provider` → `api_type` in `CreateCustomCredentialRequest`, `CustomCredentialInfo`, list/create endpoints |
| `examples/agent_service/custom_model_router.py` | `_load_yaml_models_for_provider()` → `_load_yaml_models_for_api_type()`, `_get_credential_provider()` → `_get_credential_api_type()`, YAML loading returns `api_type` field |

### Frontend

| File | Change |
|------|--------|
| `examples/web_ui/frontend/src/components/dialog/CreateCustomCredentialDialog.tsx` | Removed `PROVIDER_PRESETS`, added `API_TYPES` array; `provider` state → `apiType` state (default: `chat_completions`); removed `handleProviderChange` auto-fill |
| `examples/web_ui/frontend/src/api/types.ts` | `CustomCredentialInfo.provider` → `api_type: string`, `CreateCustomCredentialRequest.provider` → `api_type: string` |
| `examples/web_ui/frontend/src/i18n/locales/en.json` | Removed `provider`/`providerPlaceholder`, added `apiType: "API type"` |
| `examples/web_ui/frontend/src/i18n/locales/zh.json` | Removed `provider`/`providerPlaceholder`, added `apiType: "API 类型"` |

### YAML Model Files

| File | Change |
|------|--------|
| `examples/agent_service/models/GLM-5.yaml` | `provider: zhipuai` → `api_type: chat_completions` |
| `examples/agent_service/models/GLM-4_5V.yaml` | `provider: zhipuai` → `api_type: chat_completions` |
| `examples/agent_service/models/DeepSeek-V4-Flash.yaml` | `provider: deepseek` → `api_type: chat_completions` |
| `examples/agent_service/models/MiniMax-M2.yaml` | `provider: minimax` → `api_type: chat_completions` |
| `examples/agent_service/models/qwen3-vl-30b-a3b-instruct.yaml` | `provider: alibaba` → `api_type: chat_completions` |

## Verification Results

| Check | Result |
|-------|--------|
| TypeScript errors (modified files) | ✅ 0 errors |
| Python errors (modified files) | ✅ 0 errors |
| Backend `GET /custom-credential/` | ✅ 200 OK |
| Backend `POST /custom-credential/` with `api_type` | ✅ 201 Created |
| Backend list returns `api_type` field | ✅ Confirmed |
| Backend `GET /custom-model/{id}` for `chat_completions` | ✅ 5 YAML models returned |
| YAML filtering: `chat_completions` | ✅ 5 models |
| YAML filtering: `responses` | ✅ 0 models |
| YAML filtering: `messages` | ✅ 0 models |
| `api_type` key stripped from model list | ✅ Confirmed |
| Frontend dialog opens with API type dropdown | ✅ "API type" label, "Chat Completions" default |
| Frontend dialog has 3 API type options | ✅ Chat Completions / Responses / Messages |
| Test credential cleanup | ✅ Deleted after testing |

## Phase Tracking

| Phase | Status | Date |
|-------|--------|------|
| Phase 1: UNDERSTAND | ✅ Completed | 2026-08-20 |
| Phase 2: LOCATE & READ SOURCE | ✅ Completed | 2026-08-20 |
| Phase 3: DESIGN | ✅ Completed | 2026-08-20 |
| Phase 4: IMPLEMENT | ✅ Completed | 2026-08-20 |
| Phase 5: TEST | ✅ Completed | 2026-08-20 |
| Phase 6: TEST PLAN | ⏭️ Skipped (S complexity) | — |
| Phase 7: VERIFY | ⏭️ Skipped (S complexity) | — |
| Phase 8: DOCUMENT | ✅ Completed | 2026-08-20 |
| Phase 9: EXECUTE LOG | ✅ Completed | 2026-08-20 |

## Unfinished Items

None.
