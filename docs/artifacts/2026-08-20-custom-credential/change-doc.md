# Change Doc: Custom Credential + Custom Models

## Summary

Add the ability for users to create **custom credentials** (name + API base URL + API key) and manage **custom models** under those credentials. Remove custom model management from standard credentials (OpenAI, Anthropic, etc.) — standard credentials only show their built-in model list.

## Motivation

Currently, custom models are merged into ALL credentials globally, which is confusing. Users need a clean separation: standard credentials show only built-in models, custom credentials hold user-defined models.

## Design

### Backend

#### 1. New: `custom_credential_router.py`

A new router that wraps the framework's credential storage to create/list/delete custom credentials. A custom credential is stored as an `OpenAICredential` (since all YAML models are OpenAI-compatible) with a custom `base_url`.

**Endpoints:**
- `POST /custom-credential/` — Create: `{name, base_url, api_key}` → stores as `OpenAICredential(type="openai_credential", name=..., base_url=..., api_key=...)`
- `GET /custom-credential/` — List all custom credentials (filter by `base_url` being set and `name` matching a custom credential pattern, or track in a separate JSON store)
- `DELETE /custom-credential/{credential_id}` — Delete credential + its custom models

**Storage**: Track custom credential IDs in `custom_credentials.json` (a simple list of credential IDs that are "custom"). The actual credential data lives in the framework's Redis storage.

#### 2. Modify: `custom_model_router.py`

- Remove the global YAML model merge from `list_custom_models`
- Instead, YAML models are associated with custom credentials by a `provider` field in the YAML file
- When listing custom models for a credential, check if the credential is a custom credential and which provider it belongs to, then return the matching YAML models + user-added models
- Add a `provider` field to YAML model files (e.g. `provider: zhipuai`)

#### 3. Modify: `main.py`

- Register `custom_credential_router`

### Frontend

#### 4. Modify: `credential/index.tsx`

- Add a "Custom Credentials" section in the sidebar (separate from standard providers)
- Add "Add Custom Credential" button that opens the new dialog
- In the detail panel: show the "Custom" tab ONLY for custom credentials
- For standard credentials: hide the "Custom" tab

#### 5. New: `CreateCustomCredentialDialog.tsx`

Simple form with:
- Name (text input)
- API Base URL (text input, e.g. `https://open.bigmodel.cn/api/paas/v4`)
- API Key (password input)

#### 6. Update: i18n locales

Add keys for custom credential creation, listing, etc.

### YAML Model Changes

Add `provider` field to each YAML file:
- `GLM-5.yaml` → `provider: zhipuai`
- `GLM-4_5V.yaml` → `provider: zhipuai`
- `DeepSeek-V4-Flash.yaml` → `provider: deepseek`
- `MiniMax-M2.yaml` → `provider: minimax`
- `qwen3-vl-30b-a3b-instruct.yaml` → `provider: alibaba`

When creating a custom credential, the user picks an API type. YAML models for that API type are auto-attached.

### Update: Provider → API Type Migration

The original design used a `provider` field (ZhipuAI, DeepSeek, MiniMax, Alibaba, Custom) to associate YAML models with custom credentials. This has been **replaced** with a simpler `api_type` field that directly reflects the request/response format:

**API Types:**
- `chat_completions` — OpenAI Chat Completions format (default)
- `responses` — OpenAI Responses API format
- `messages` — Anthropic Messages API format

**Rationale:** The provider presets added unnecessary complexity. What matters for model compatibility is the API format, not the vendor. All 5 YAML model files now use `api_type: chat_completions` instead of `provider: <vendor>`.

**Changes from original design:**
- `CreateCustomCredentialDialog.tsx`: `PROVIDER_PRESETS` array removed, replaced with `API_TYPES` array (3 options). No auto-fill of base URL.
- `custom_credential_router.py`: `provider` field → `api_type` field (default: `chat_completions`) in both `CreateCustomCredentialRequest` and `CustomCredentialInfo`.
- `custom_model_router.py`: `_load_yaml_models_for_provider()` → `_load_yaml_models_for_api_type()`, `_get_credential_provider()` → `_get_credential_api_type()`.
- `types.ts`: `CustomCredentialInfo.provider` → `api_type`, `CreateCustomCredentialRequest.provider` → `api_type`.
- `en.json` / `zh.json`: `provider` / `providerPlaceholder` keys removed, `apiType` key added.
- 5 YAML files: `provider: <vendor>` → `api_type: chat_completions`.

## Impact Assessment

| Dimension | Impact |
|-----------|--------|
| New files | `custom_credential_router.py`, `CreateCustomCredentialDialog.tsx` |
| Modified files | `custom_model_router.py`, `main.py`, `credential/index.tsx`, `types.ts`, `customModel.ts`, `en.json`, `zh.json`, 5 YAML files |
| Framework source | None — all changes in `examples/` |
| DB/Storage | No schema changes — uses existing Redis storage + JSON files |
| Complexity | **S** (Small) — provider→api_type is a field rename, no structural changes |

## Complexity: S

Phases 6-7 skipped. Phases 1-5, 8-9 executed.
