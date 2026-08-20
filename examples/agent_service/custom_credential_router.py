# -*- coding: utf-8 -*-
"""Custom credential management router for the example agent service.

This router lets users create, list, and delete **custom credentials** —
credentials with a user-defined name, API base URL, and API key.  Custom
credentials are stored as ``OpenAICredential`` instances in the framework's
Redis storage (since all pre-configured YAML models use the OpenAI-compatible
API format), and tracked separately in ``custom_credentials.json``.

Custom models (user-added or YAML) are managed under custom credentials
only — standard credentials (OpenAI, Anthropic, etc.) show only their
built-in model list.

The router is registered in ``main.py`` via ``app.include_router()``
after ``create_app()`` returns — no core agentscope code is modified.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agentscope.app._service import ResourceAccessService
from agentscope.app.access import ResourceKind
from agentscope.app.deps import (
    get_current_user_id,
    get_resource_access_service,
    get_storage,
)
from agentscope.app.storage import StorageBase
from agentscope.credential import OpenAICredential

custom_credential_router = APIRouter(
    prefix="/custom-credential",
    tags=["custom-credential"],
    responses={404: {"description": "Not found"}},
)

# ── Storage ────────────────────────────────────────────────────────────

_STORE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "custom_credentials.json",
)


def _load_store() -> dict[str, dict[str, Any]]:
    """Load the custom-credentials store from disk.

    Returns:
        A dict mapping ``credential_id`` to a metadata dict with
        ``api_type`` and ``name`` keys.
    """
    if not os.path.exists(_STORE_PATH):
        return {}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_store(data: dict[str, dict[str, Any]]) -> None:
    """Persist the custom-credentials store to disk.

    Args:
        data: The full store dict to write.
    """
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Schemas ────────────────────────────────────────────────────────────


class CreateCustomCredentialRequest(BaseModel):
    """Request body for creating a custom credential.

    Attributes:
        name: User-facing display name (e.g. "My GLM Endpoint").
        base_url: The API base URL (e.g.
            ``https://open.bigmodel.cn/api/paas/v4``).
        api_key: The API key for authentication.
        api_type: The request/response format for models in this
            credential. One of ``"chat_completions"``,
            ``"responses"``, ``"messages"``. Pre-configured YAML
            models with a matching ``api_type`` are auto-attached.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Display name for this credential.",
    )
    base_url: str = Field(
        ...,
        min_length=1,
        description="The API base URL for the OpenAI-compatible endpoint.",
    )
    api_key: str = Field(
        ...,
        min_length=1,
        description="The API key for authentication.",
    )
    api_type: str = Field(
        default="chat_completions",
        description=(
            "The request/response format for models in this credential. "
            'One of "chat_completions", "responses", "messages". '
            "Pre-configured YAML models with a matching api_type are "
            "auto-attached."
        ),
    )


class CustomCredentialInfo(BaseModel):
    """Metadata for a custom credential.

    Attributes:
        credential_id: The framework-assigned credential ID.
        name: The display name.
        base_url: The API base URL.
        api_type: The request/response format for models.
    """

    credential_id: str = Field(..., description="The credential ID.")
    name: str = Field(..., description="The display name.")
    base_url: str = Field(..., description="The API base URL.")
    api_type: str = Field(
        default="chat_completions",
        description="The request/response format for models.",
    )


class ListCustomCredentialsResponse(BaseModel):
    """Response listing all custom credentials."""

    credentials: list[CustomCredentialInfo] = Field(
        ...,
        description="The custom credentials.",
    )


class CreateCustomCredentialResponse(BaseModel):
    """Response after creating a custom credential."""

    credential_id: str = Field(
        ...,
        description="The server-assigned credential identifier.",
    )


# ── Endpoints ──────────────────────────────────────────────────────────


@custom_credential_router.get(
    "/",
    response_model=ListCustomCredentialsResponse,
    summary="List all custom credentials",
)
async def list_custom_credentials(
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> ListCustomCredentialsResponse:
    """Return all custom credentials for the authenticated user.

    Args:
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        ``ListCustomCredentialsResponse`` with the custom credential list.
    """
    store = _load_store()
    result: list[CustomCredentialInfo] = []
    for cred_id, meta in store.items():
        # Verify the credential still exists in storage.
        try:
            record = await access.resolve_credential(user_id, cred_id)
        except HTTPException:
            continue
        result.append(
            CustomCredentialInfo(
                credential_id=cred_id,
                name=meta.get("name", record.data.get("name", cred_id)),
                base_url=meta.get(
                    "base_url",
                    record.data.get("base_url", ""),
                ),
                api_type=meta.get("api_type", "chat_completions"),
            )
        )
    return ListCustomCredentialsResponse(credentials=result)


@custom_credential_router.post(
    "/",
    response_model=CreateCustomCredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom credential",
)
async def create_custom_credential(
    body: CreateCustomCredentialRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> CreateCustomCredentialResponse:
    """Create a new custom credential.

    Stores an :class:`OpenAICredential` with the given name, base URL,
    and API key in the framework's storage, then tracks it in the
    custom credentials JSON store.

    Args:
        body: The request body with name, base_url, api_key, api_type.
        user_id: Injected user ID.
        storage: Injected storage backend.

    Returns:
        ``CreateCustomCredentialResponse`` with the new credential ID.
    """
    credential = OpenAICredential(
        name=body.name,
        api_key=body.api_key,
        base_url=body.base_url,
    )
    credential_id = await storage.upsert_credential(user_id, credential)

    # Track in custom credentials store
    store = _load_store()
    store[credential_id] = {
        "name": body.name,
        "base_url": body.base_url,
        "api_type": body.api_type,
    }
    _save_store(store)

    return CreateCustomCredentialResponse(credential_id=credential_id)


@custom_credential_router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom credential",
)
async def delete_custom_credential(
    credential_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> None:
    """Delete a custom credential and its custom models.

    Removes the credential from the framework's storage and from the
    custom credentials JSON store. Also removes any custom models
    registered under this credential from ``custom_models.json``.

    Args:
        credential_id: The credential to delete.
        user_id: Injected user ID.
        storage: Injected storage backend.
        access: Injected resource access service.

    Raises:
        HTTPException: 404 if the credential is not found.
    """
    # Verify ownership and edit permission
    owner_id, _ = await access.resolve_for_edit(
        user_id,
        ResourceKind.CREDENTIAL,
        credential_id,
    )

    # Delete from framework storage
    try:
        await storage.delete_credential(owner_id, credential_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential {credential_id!r} not found.",
        ) from exc

    # Remove from custom credentials store
    store = _load_store()
    store.pop(credential_id, None)
    _save_store(store)

    # Remove any custom models registered under this credential
    models_store_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "custom_models.json",
    )
    if os.path.exists(models_store_path):
        try:
            with open(models_store_path, "r", encoding="utf-8") as f:
                models_store = json.load(f)
            models_store.pop(credential_id, None)
            with open(models_store_path, "w", encoding="utf-8") as f:
                json.dump(models_store, f, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, OSError):
            pass
