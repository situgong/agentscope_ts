# -*- coding: utf-8 -*-
"""Custom model management router for the example agent service.

This router lets users add, remove, and connection-test custom model
names under a given credential.  Custom models are model names that the
user deployed themselves (e.g. a fine-tuned model behind an OpenAI-
compatible endpoint) and that are NOT listed in the built-in model
catalog returned by ``/model/``.

Storage is a simple JSON file (``custom_models.json``) next to
``main.py`` — no database changes are needed and the file survives
restarts.

The router is registered in ``main.py`` via ``app.include_router()``
after ``create_app()`` returns — no core agentscope code is modified.
"""
from __future__ import annotations

import json
import os
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agentscope.app._service import ResourceAccessService
from agentscope.app.deps import get_current_user_id, get_resource_access_service
from agentscope.app._service._model import get_model
from agentscope.app.storage import ChatModelConfig
from agentscope.message import UserMsg, TextBlock

custom_model_router = APIRouter(
    prefix="/custom-model",
    tags=["custom-model"],
    responses={404: {"description": "Not found"}},
)

# ── Storage ────────────────────────────────────────────────────────────

_STORE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "custom_models.json",
)

_YAML_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models",
)


def _load_yaml_models() -> list[dict[str, Any]]:
    """Load model definitions from YAML files in the ``models/`` directory.

    These are pre-configured model cards shipped with the example
    service (e.g. GLM-5, DeepSeek-V4-Flash). They are merged with
    user-added custom models in :func:`list_custom_models`.

    Returns:
        A list of model info dicts in the same shape as
        :class:`CustomModelInfo`.
    """
    if not os.path.isdir(_YAML_MODELS_DIR):
        return []

    models: list[dict[str, Any]] = []
    for filename in sorted(os.listdir(_YAML_MODELS_DIR)):
        if not filename.endswith((".yaml", ".yml")):
            continue
        filepath = os.path.join(_YAML_MODELS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if not config or "name" not in config:
                continue
            models.append(
                {
                    "name": config["name"],
                    "label": config.get("label", config["name"]),
                    "status": config.get("status", "active"),
                    "input_types": config.get(
                        "input_types", ["text/plain"],
                    ),
                    "output_types": config.get(
                        "output_types", ["text/plain"],
                    ),
                    "context_size": config.get("context_size"),
                    "output_size": config.get("output_size"),
                }
            )
        except (yaml.YAMLError, OSError, KeyError):
            continue
    return models


def _load_store() -> dict[str, list[dict[str, Any]]]:
    """Load the custom-models store from disk.

    Returns:
        A dict mapping ``credential_id`` to a list of custom model
        info dicts.
    """
    if not os.path.exists(_STORE_PATH):
        return {}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_store(data: dict[str, list[dict[str, Any]]]) -> None:
    """Persist the custom-models store to disk.

    Args:
        data: The full store dict to write.
    """
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _migrate_legacy(store: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Migrate old ``list[str]`` format to new ``list[dict]`` format.

    Args:
        store: The raw loaded store, possibly in legacy format.

    Returns:
        The store with all entries in ``list[dict]`` format.
    """
    for cred_id, models in store.items():
        if models and isinstance(models[0], str):
            store[cred_id] = [
                {
                    "name": name,
                    "label": name,
                    "status": "active",
                    "input_types": ["text/plain"],
                    "output_types": ["text/plain"],
                    "context_size": None,
                    "output_size": None,
                }
                for name in models
            ]
    return store


# ── Schemas ────────────────────────────────────────────────────────────


class CustomModelInfo(BaseModel):
    """Full model-card-like info for a custom model."""

    name: str = Field(..., description="The model name sent to the API.")
    label: str = Field(..., description="Display label for the model.")
    status: str = Field("active", description="Model status: active/deprecated/sunset.")
    input_types: list[str] = Field(
        default_factory=lambda: ["text/plain"],
        description="Accepted input MIME types.",
    )
    output_types: list[str] = Field(
        default_factory=lambda: ["text/plain"],
        description="Produced output MIME types.",
    )
    context_size: int | None = Field(
        None,
        description="Maximum context window in tokens, if known.",
    )
    output_size: int | None = Field(
        None,
        description="Maximum output tokens, if known.",
    )


class CustomModelListResponse(BaseModel):
    """Response listing custom models for a credential."""

    models: list[CustomModelInfo] = Field(
        ...,
        description="The custom models registered under this credential.",
    )


class AddCustomModelRequest(BaseModel):
    """Request body for adding a custom model."""

    name: str = Field(
        ...,
        min_length=1,
        description="The model name to register (sent to the API).",
    )
    label: str | None = Field(
        None,
        description="Optional display label. Defaults to the model name.",
    )
    input_types: list[str] | None = Field(
        None,
        description="Accepted input MIME types. Defaults to text/plain.",
    )
    output_types: list[str] | None = Field(
        None,
        description="Produced output MIME types. Defaults to text/plain.",
    )
    context_size: int | None = Field(
        None,
        description="Maximum context window in tokens, if known.",
    )
    output_size: int | None = Field(
        None,
        description="Maximum output tokens, if known.",
    )


class TestModelRequest(BaseModel):
    """Request body for connection-testing a model."""

    credential_id: str = Field(
        ...,
        description="The credential to use for the test call.",
    )
    model_name: str = Field(
        ...,
        min_length=1,
        description="The model name to test.",
    )


class TestModelResponse(BaseModel):
    """Result of a connection test."""

    success: bool = Field(..., description="Whether the test succeeded.")
    message: str = Field(
        ...,
        description="A human-readable result or error message.",
    )
    reply: str | None = Field(
        None,
        description="The model's reply text (on success).",
    )


# ── Endpoints ──────────────────────────────────────────────────────────
#
# IMPORTANT: The ``/test`` route MUST be registered before the
# ``/{credential_id}`` routes, otherwise FastAPI will match
# ``POST /custom-model/test`` as ``credential_id="test"``.


@custom_model_router.post(
    "/test",
    response_model=TestModelResponse,
    summary="Connection-test a model",
)
async def test_model(
    body: TestModelRequest,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> TestModelResponse:
    """Send a minimal chat request to verify a model is reachable.

    Builds a :class:`ChatModelBase` from the credential + model name,
    sends ``"Hi"`` as a user message, and returns the reply text.

    Args:
        body: The request body with ``credential_id`` and ``model_name``.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        ``TestModelResponse`` with success status and reply text.
    """
    # Resolve the actual credential type so non-openai providers work too.
    try:
        record = await access.resolve_credential(
            user_id,
            body.credential_id,
        )
    except HTTPException as exc:
        raise exc

    config = ChatModelConfig(
        type=record.data.get("type", "openai_credential"),
        credential_id=body.credential_id,
        model=body.model_name,
        parameters={},
    )

    try:
        model = await get_model(user_id, config, access)
    except Exception as exc:  # pylint: disable=broad-except
        return TestModelResponse(
            success=False,
            message=f"Failed to build model: {exc}",
            reply=None,
        )

    # Send a minimal test message.
    test_msg = UserMsg(name="test", content="Hi")
    try:
        res = await model([test_msg])
        # Extract text from the response.
        reply_text = ""
        if hasattr(res, "content") and res.content:
            for block in res.content:
                if isinstance(block, TextBlock):
                    reply_text += block.text
        return TestModelResponse(
            success=True,
            message="Connection successful.",
            reply=reply_text or None,
        )
    except Exception as exc:  # pylint: disable=broad-except
        return TestModelResponse(
            success=False,
            message=f"Connection failed: {exc}",
            reply=None,
        )


@custom_model_router.get(
    "/{credential_id}",
    response_model=CustomModelListResponse,
    summary="List custom models for a credential",
)
async def list_custom_models(
    credential_id: str,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> CustomModelListResponse:
    """Return the custom models registered under *credential_id*.

    Args:
        credential_id: The credential whose custom models to list.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        ``CustomModelListResponse`` with the model info list.
    """
    # Validate that the credential exists and is accessible.
    try:
        await access.resolve_credential(user_id, credential_id)
    except HTTPException as exc:
        raise exc

    store = _migrate_legacy(_load_store())
    raw = store.get(credential_id, [])
    # Merge pre-configured YAML models with user-added custom models.
    # YAML models are shared across all credentials; user-added models
    # are per-credential. Duplicates (by name) are deduplicated, with
    # user-added models taking precedence.
    yaml_models = _load_yaml_models()
    yaml_names = {m["name"] for m in raw}
    merged = list(raw) + [
        m for m in yaml_models if m["name"] not in yaml_names
    ]
    models = [CustomModelInfo(**m) for m in merged]
    return CustomModelListResponse(models=models)


@custom_model_router.post(
    "/{credential_id}",
    response_model=CustomModelListResponse,
    summary="Add a custom model to a credential",
)
async def add_custom_model(
    credential_id: str,
    body: AddCustomModelRequest,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> CustomModelListResponse:
    """Register a custom model under *credential_id*.

    Args:
        credential_id: The credential to attach the model to.
        body: The request body containing model info.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        ``CustomModelListResponse`` with the updated model list.

    Raises:
        HTTPException 404: Credential not found.
        HTTPException 409: Model name already registered.
    """
    # Validate credential access.
    try:
        await access.resolve_credential(user_id, credential_id)
    except HTTPException as exc:
        raise exc

    store = _migrate_legacy(_load_store())
    models = store.setdefault(credential_id, [])
    name = body.name.strip()
    if any(m.get("name") == name for m in models):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model '{name}' is already registered.",
        )
    models.append(
        {
            "name": name,
            "label": body.label or name,
            "status": "active",
            "input_types": body.input_types or ["text/plain"],
            "output_types": body.output_types or ["text/plain"],
            "context_size": body.context_size,
            "output_size": body.output_size,
        }
    )
    _save_store(store)
    return CustomModelListResponse(models=[CustomModelInfo(**m) for m in models])


@custom_model_router.delete(
    "/{credential_id}/{model_name}",
    response_model=CustomModelListResponse,
    summary="Remove a custom model from a credential",
)
async def remove_custom_model(
    credential_id: str,
    model_name: str,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> CustomModelListResponse:
    """Remove a custom model from *credential_id*.

    Args:
        credential_id: The credential to remove the model from.
        model_name: The model name to remove.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        ``CustomModelListResponse`` with the updated model list.

    Raises:
        HTTPException 404: Credential or model not found.
    """
    # Validate credential access.
    try:
        await access.resolve_credential(user_id, credential_id)
    except HTTPException as exc:
        raise exc

    store = _migrate_legacy(_load_store())
    models = store.get(credential_id, [])
    idx = next((i for i, m in enumerate(models) if m.get("name") == model_name), -1)
    if idx == -1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found.",
        )
    models.pop(idx)
    if not models:
        del store[credential_id]
    _save_store(store)
    return CustomModelListResponse(models=[CustomModelInfo(**m) for m in models])
