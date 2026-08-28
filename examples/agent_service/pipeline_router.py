# -*- coding: utf-8 -*-
"""Custom pipeline router for the example agent service.

This router implements a **per-step instruction pipeline**: each agent
in the chain receives its own instruction message combined with the
previous agent's output.

The chain logic lives in :class:`~sequential_pipeline.SequentialPipeline`,
which implements the framework's
:class:`~agentscope.pipeline.PipelineProtocol`.  This router is a thin
HTTP wrapper that creates a ``SequentialPipeline`` and either collects
results (sync) or streams events (SSE).

The router is registered in ``main.py`` via ``app.include_router()``
after ``create_app()`` returns — no core agentscope code is modified.

.. note::

    Pipeline runs are **stateless**: each agent is assembled fresh from
    its stored config without session state, workspace tools, or
    middlewares.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agentscope.app._service import ResourceAccessService
from agentscope.app.deps import get_current_user_id, get_resource_access_service
from agentscope.message import Msg, UserMsg

from sequential_pipeline import (
    PipelineStep,
    PipelineSubStep,
    SequentialPipeline,
    assemble_agent,
)

pipeline_router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
    responses={404: {"description": "Not found"}},
)


# ── Schemas (request/response — step schemas imported from
#    sequential_pipeline.py) ────────────────────────────────────────────


class RunPipelineRequest(BaseModel):
    """Request body for running a pipeline."""

    steps: list[PipelineStep] = Field(
        ...,
        min_length=1,
        description="The ordered pipeline steps.",
    )
    chat_model_config: dict[str, Any] = Field(
        ...,
        description=(
            "The chat model configuration dict (as ChatModelConfig "
            "serialised). Shared by all agents in the pipeline."
        ),
    )


class PipelineStepResult(BaseModel):
    """The result from a single pipeline step."""

    step_index: int = Field(..., description="The 0-based step index.")
    agent_id: str = Field(..., description="The agent ID.")
    agent_name: str = Field(..., description="The agent name.")
    instruction: str = Field(..., description="The instruction that was given.")
    reply: Msg = Field(..., description="The agent's initial reply message.")
    sub_results: list["PipelineStepResult"] = Field(
        default_factory=list,
        description="Results from sub-steps, if any.",
    )
    final_reply: Msg | None = Field(
        default=None,
        description=(
            "The agent's final reply after processing sub-step outputs. "
            "Only set when the step has sub-steps; the agent is re-run "
            "with the sub-step outputs to produce a consolidated result."
        ),
    )


# Resolve the forward reference in sub_results
PipelineStepResult.model_rebuild()


class RunPipelineResponse(BaseModel):
    """Response body for a pipeline run."""

    results: list[PipelineStepResult] = Field(
        ...,
        description="One result per step, in order.",
    )


# ── SSE helper ─────────────────────────────────────────────────────────


def _sse(data: dict[str, Any]) -> str:
    """Format a dict as an SSE ``data:`` frame.

    Args:
        data: The payload to serialise.

    Returns:
        ``data: {json}\\n\\n``
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Sync endpoint ──────────────────────────────────────────────────────


@pipeline_router.post(
    "/run",
    response_model=RunPipelineResponse,
    summary="Run a pipeline with per-step instructions",
)
async def run_pipeline(
    request: RunPipelineRequest,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> RunPipelineResponse:
    """Run a pipeline where each agent gets its own instruction.

    Creates a :class:`~sequential_pipeline.SequentialPipeline` and
    collects the results from each step.

    Args:
        request: The pipeline request with steps and model config.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        The results from each step.
    """
    pipe = SequentialPipeline(
        steps=request.steps,
        chat_model_config=request.chat_model_config,
        user_id=user_id,
        access=access,
    )

    results: list[PipelineStepResult] = []
    prev_reply: Msg | None = None

    for idx, step in enumerate(request.steps):
        agent = await assemble_agent(
            user_id,
            step.agent_id,
            request.chat_model_config,
            access,
        )

        # Build the input: instruction + previous output (if any)
        if prev_reply is not None:
            prev_text = prev_reply.get_text_content() or ""
            combined_instruction = (
                f"Previous step output:\n{prev_text}\n\n"
                f"Your instruction:\n{step.instruction}"
            )
            inputs: Msg | list[Msg] = UserMsg(
                name="pipeline",
                content=combined_instruction,
            )
        else:
            inputs = UserMsg(name="pipeline", content=step.instruction)

        reply = await agent.reply(inputs)

        # Execute sub-steps: each receives the parent step's output
        sub_results: list[PipelineStepResult] = []
        current_reply = reply
        for sub_idx, sub_step in enumerate(step.sub_steps):
            sub_agent = await assemble_agent(
                user_id,
                sub_step.agent_id,
                request.chat_model_config,
                access,
            )
            parent_text = current_reply.get_text_content() or ""
            sub_combined = (
                f"Previous output:\n{parent_text}\n\n"
                f"Your instruction:\n{sub_step.instruction}"
            )
            sub_inputs = UserMsg(name="pipeline", content=sub_combined)
            sub_reply = await sub_agent.reply(sub_inputs)
            sub_results.append(
                PipelineStepResult(
                    step_index=sub_idx,
                    agent_id=sub_step.agent_id,
                    agent_name=sub_agent.name,
                    instruction=sub_step.instruction,
                    reply=sub_reply,
                ),
            )
            current_reply = sub_reply

        # If there were sub-steps, re-run the parent agent with the
        # sub-step outputs so it can consolidate them into a final reply.
        final_reply: Msg | None = None
        if sub_results:
            sub_outputs = "\n\n".join(
                f"Sub-step {sub_idx + 1} ({sr.agent_name}) output:\n"
                f"{sr.reply.get_text_content() or ''}"
                for sub_idx, sr in enumerate(sub_results)
            )
            final_instruction = (
                f"Your initial output:\n{reply.get_text_content() or ''}\n\n"
                f"Sub-step outputs:\n{sub_outputs}\n\n"
                f"Please consolidate the above into a final response "
                f"based on your original instruction:\n{step.instruction}"
            )
            final_inputs = UserMsg(name="pipeline", content=final_instruction)
            final_reply = await agent.reply(final_inputs)
            current_reply = final_reply

        results.append(
            PipelineStepResult(
                step_index=idx,
                agent_id=step.agent_id,
                agent_name=agent.name,
                instruction=step.instruction,
                reply=reply,
                sub_results=sub_results,
                final_reply=final_reply,
            ),
        )

        prev_reply = current_reply

    return RunPipelineResponse(results=results)


# ── SSE streaming endpoint ─────────────────────────────────────────────


@pipeline_router.post(
    "/run/stream",
    summary="Run a pipeline with streaming SSE output",
)
async def run_pipeline_stream(
    request: RunPipelineRequest,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> StreamingResponse:
    """Run a pipeline, streaming each step's result as an SSE event.

    Events emitted (each as ``data: {json}\\n\\n``):

    - ``{"type": "step_start", "step_index": N, ...}`` — before a
      parent step runs.
    - ``{"type": "step_done", "step_index": N, ...}`` — after a parent
      step completes, includes the agent's reply.
    - ``{"type": "sub_step_done", "step_index": N, "sub_step_index": M, ...}``
      — after a sub-step completes.
    - ``{"type": "step_final", "step_index": N, ...}`` — after the parent
      agent re-runs with sub-step outputs to produce a consolidated reply.
      Only emitted when the step has sub-steps.
    - ``{"type": "pipeline_done", "total_steps": N}`` — all steps done.
    - ``{"type": "error", "message": "..."}`` — on failure.

    Args:
        request: The pipeline request with steps and model config.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` media type.
    """

    async def _stream() -> AsyncGenerator[str, None]:
        prev_reply: Msg | None = None

        for idx, step in enumerate(request.steps):
            try:
                agent = await assemble_agent(
                    user_id,
                    step.agent_id,
                    request.chat_model_config,
                    access,
                )
            except HTTPException as exc:
                yield _sse(
                    {
                        "type": "error",
                        "step_index": idx,
                        "message": exc.detail,
                    },
                )
                return

            yield _sse(
                {
                    "type": "step_start",
                    "step_index": idx,
                    "agent_id": step.agent_id,
                    "agent_name": agent.name,
                },
            )

            # Build the input: instruction + previous output (if any)
            if prev_reply is not None:
                prev_text = prev_reply.get_text_content() or ""
                combined_instruction = (
                    f"Previous step output:\n{prev_text}\n\n"
                    f"Your instruction:\n{step.instruction}"
                )
                inputs: Msg | list[Msg] = UserMsg(
                    name="pipeline",
                    content=combined_instruction,
                )
            else:
                inputs = UserMsg(name="pipeline", content=step.instruction)

            try:
                reply = await agent.reply(inputs)
            except Exception as exc:
                yield _sse(
                    {
                        "type": "error",
                        "step_index": idx,
                        "message": str(exc),
                    },
                )
                return

            reply_data = reply.model_dump(mode="json")
            yield _sse(
                {
                    "type": "step_done",
                    "step_index": idx,
                    "agent_id": step.agent_id,
                    "agent_name": agent.name,
                    "instruction": step.instruction,
                    "reply": reply_data,
                },
            )

            # Execute sub-steps
            current_reply = reply
            sub_replies: list[Msg] = []
            for sub_idx, sub_step in enumerate(step.sub_steps):
                try:
                    sub_agent = await assemble_agent(
                        user_id,
                        sub_step.agent_id,
                        request.chat_model_config,
                        access,
                    )
                except HTTPException as exc:
                    yield _sse(
                        {
                            "type": "error",
                            "step_index": idx,
                            "sub_step_index": sub_idx,
                            "message": exc.detail,
                        },
                    )
                    return

                parent_text = current_reply.get_text_content() or ""
                sub_combined = (
                    f"Previous output:\n{parent_text}\n\n"
                    f"Your instruction:\n{sub_step.instruction}"
                )
                sub_inputs = UserMsg(name="pipeline", content=sub_combined)
                try:
                    sub_reply = await sub_agent.reply(sub_inputs)
                except Exception as exc:
                    yield _sse(
                        {
                            "type": "error",
                            "step_index": idx,
                            "sub_step_index": sub_idx,
                            "message": str(exc),
                        },
                    )
                    return

                yield _sse(
                    {
                        "type": "sub_step_done",
                        "step_index": idx,
                        "sub_step_index": sub_idx,
                        "agent_id": sub_step.agent_id,
                        "agent_name": sub_agent.name,
                        "instruction": sub_step.instruction,
                        "reply": sub_reply.model_dump(mode="json"),
                    },
                )
                current_reply = sub_reply
                sub_replies.append(sub_reply)

            # If there were sub-steps, re-run the parent agent with the
            # sub-step outputs so it can consolidate them into a final reply.
            if step.sub_steps:
                sub_outputs = "\n\n".join(
                    f"Sub-step {sub_idx + 1} output:\n"
                    f"{sr.get_text_content() or ''}"
                    for sub_idx, sr in enumerate(sub_replies)
                )
                final_instruction = (
                    f"Your initial output:\n{reply.get_text_content() or ''}\n\n"
                    f"Sub-step outputs:\n{sub_outputs}\n\n"
                    f"Please consolidate the above into a final response "
                    f"based on your original instruction:\n{step.instruction}"
                )
                final_inputs = UserMsg(name="pipeline", content=final_instruction)
                try:
                    final_reply = await agent.reply(final_inputs)
                except Exception as exc:
                    yield _sse(
                        {
                            "type": "error",
                            "step_index": idx,
                            "message": str(exc),
                        },
                    )
                    return

                yield _sse(
                    {
                        "type": "step_final",
                        "step_index": idx,
                        "agent_id": step.agent_id,
                        "agent_name": agent.name,
                        "reply": final_reply.model_dump(mode="json"),
                    },
                )
                current_reply = final_reply

            prev_reply = current_reply

        yield _sse(
            {
                "type": "pipeline_done",
                "total_steps": len(request.steps),
            },
        )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
