# -*- coding: utf-8 -*-
"""Goal pipeline router for the example agent service.

This router exposes the framework's
:class:`~agentscope.pipeline.GoalPipeline` via HTTP endpoints.  The
``GoalPipeline`` runs an executor agent and a verifier agent in a loop
until the goal is achieved (or ``max_iters`` is reached, or the verifier
judges the goal impossible).

The router is registered in ``main.py`` via ``app.include_router()``
after ``create_app()`` returns — no core agentscope code is modified.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agentscope.app._service import ResourceAccessService
from agentscope.app.deps import (
    get_current_user_id,
    get_resource_access_service,
)
from agentscope.event import AgentEvent
from agentscope.message import Msg, UserMsg
from agentscope.pipeline import GoalPipeline

from sequential_pipeline import assemble_agent

goal_pipeline_router = APIRouter(
    prefix="/pipeline/goal",
    tags=["pipeline"],
    responses={404: {"description": "Not found"}},
)


# ── Schemas ───────────────────────────────────────────────────────────


class RunGoalPipelineRequest(BaseModel):
    """Request body for running a goal pipeline.

    Args:
        executor_agent_id: The stored agent ID for the executor.
        verifier_agent_id: The stored agent ID for the verifier.
        instruction: The goal instruction for the executor.
        chat_model_config: The chat model configuration dict.
        max_iters: Maximum goal achievement attempts. Defaults to 10.
    """

    executor_agent_id: str = Field(
        ...,
        description="The ID of the executor agent.",
    )
    verifier_agent_id: str = Field(
        ...,
        description="The ID of the verifier agent.",
    )
    instruction: str = Field(
        ...,
        description="The goal instruction for the executor.",
    )
    chat_model_config: dict[str, Any] = Field(
        ...,
        description=(
            "The chat model configuration dict (as ChatModelConfig "
            "serialised). Shared by executor and verifier."
        ),
    )
    max_iters: int = Field(
        default=10,
        description="Maximum goal achievement attempts.",
    )


class GoalIterationResult(BaseModel):
    """The result of one executor-verifier iteration.

    Args:
        iteration: The 1-based iteration number.
        execution_report: The executor's achievement report.
        verification_result: The verifier's verdict
            (``pass``/``fail``/``impossible``).
        verification_message: The verifier's explanation.
    """

    iteration: int = Field(..., description="The 1-based iteration number.")
    execution_report: str | None = Field(
        default=None,
        description="The executor's achievement report.",
    )
    verification_result: str | None = Field(
        default=None,
        description="The verifier's verdict (pass/fail/impossible).",
    )
    verification_message: str | None = Field(
        default=None,
        description="The verifier's explanation.",
    )


class RunGoalPipelineResponse(BaseModel):
    """Response body for a goal pipeline run.

    Args:
        iterations: Results from each iteration.
        final_status: The final status
            (``pass``/``impossible``/``max_iters_exceeded``).
    """

    iterations: list[GoalIterationResult] = Field(
        default_factory=list,
        description="Results from each iteration.",
    )
    final_status: str = Field(
        ...,
        description=(
            "The final status: 'pass', 'impossible', or "
            "'max_iters_exceeded'."
        ),
    )


# ── SSE helper ────────────────────────────────────────────────────────


def _sse(data: dict[str, Any]) -> str:
    """Format a dict as an SSE ``data:`` frame.

    Args:
        data: The payload to serialise.

    Returns:
        ``data: {json}\\n\\n``
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────


@goal_pipeline_router.post(
    "/run",
    response_model=RunGoalPipelineResponse,
    summary="Run a goal pipeline (executor + verifier loop)",
)
async def run_goal_pipeline(
    request: RunGoalPipelineRequest,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> RunGoalPipelineResponse:
    """Run a goal pipeline where an executor and verifier iterate.

    The executor attempts the goal, the verifier checks the result,
    and the loop continues until the verifier passes or ``max_iters``
    is reached.

    Args:
        request: The goal pipeline request.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        The results from each iteration and the final status.
    """
    # Assemble executor and verifier agents
    try:
        executor = await assemble_agent(
            user_id,
            request.executor_agent_id,
            request.chat_model_config,
            access,
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Executor agent {request.executor_agent_id!r} not found.",
        ) from exc

    try:
        verifier = await assemble_agent(
            user_id,
            request.verifier_agent_id,
            request.chat_model_config,
            access,
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verifier agent {request.verifier_agent_id!r} not found.",
        ) from exc

    # Create the goal pipeline
    pipe = GoalPipeline(
        executor=executor,
        verifier=verifier,
        max_iters=request.max_iters,
    )

    # Run the pipeline
    inputs = UserMsg(name="user", content=request.instruction)

    iterations: list[GoalIterationResult] = []
    final_status = "max_iters_exceeded"
    iter_num = 0

    async for event in pipe.reply_stream(inputs=inputs):
        if isinstance(event, Msg) and event.finished_reason:
            # Check for structured output
            if event.structured_output:
                if "report" in event.structured_output:
                    # Executor finished
                    iter_num += 1
                    iterations.append(
                        GoalIterationResult(
                            iteration=iter_num,
                            execution_report=event.structured_output.get(
                                "report",
                            ),
                        ),
                    )
                elif "result" in event.structured_output:
                    # Verifier finished
                    if iterations:
                        last = iterations[-1]
                        iterations[-1] = GoalIterationResult(
                            iteration=last.iteration,
                            execution_report=last.execution_report,
                            verification_result=event.structured_output.get(
                                "result",
                            ),
                            verification_message=event.structured_output.get(
                                "message",
                            ),
                        )
                    result = event.structured_output.get("result")
                    if result in ("pass", "impossible"):
                        final_status = result

    return RunGoalPipelineResponse(
        iterations=iterations,
        final_status=final_status,
    )


@goal_pipeline_router.post(
    "/run/stream",
    summary="Run a goal pipeline with streaming SSE output",
)
async def run_goal_pipeline_stream(
    request: RunGoalPipelineRequest,
    user_id: str = Depends(get_current_user_id),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> StreamingResponse:
    """Run a goal pipeline, streaming events as SSE.

    Events emitted (each as ``data: {json}\\n\\n``):

    - ``{"type": "executor_start", "iteration": N}`` — executor begins.
    - ``{"type": "executor_done", "iteration": N, "report": "..."}`` —
      executor finished with an achievement report.
    - ``{"type": "verifier_start", "iteration": N}`` — verifier begins.
    - ``{"type": "verifier_done", "iteration": N, "result": "pass|fail|impossible", "message": "..."}`` —
      verifier finished.
    - ``{"type": "pipeline_done", "final_status": "..."}`` — pipeline
      finished.
    - ``{"type": "error", "message": "..."}`` — on failure.

    Args:
        request: The goal pipeline request.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` media type.
    """
    async def _stream() -> AsyncGenerator[str, None]:
        try:
            executor = await assemble_agent(
                user_id,
                request.executor_agent_id,
                request.chat_model_config,
                access,
            )
        except HTTPException as exc:
            yield _sse(
                {"type": "error", "message": exc.detail},
            )
            return

        try:
            verifier = await assemble_agent(
                user_id,
                request.verifier_agent_id,
                request.chat_model_config,
                access,
            )
        except HTTPException as exc:
            yield _sse(
                {"type": "error", "message": exc.detail},
            )
            return

        pipe = GoalPipeline(
            executor=executor,
            verifier=verifier,
            max_iters=request.max_iters,
        )

        inputs = UserMsg(name="user", content=request.instruction)
        iter_num = 0
        final_status = "max_iters_exceeded"
        expecting_executor = True

        try:
            async for event in pipe.reply_stream(inputs=inputs):
                if isinstance(event, Msg) and event.finished_reason:
                    if event.structured_output:
                        if "report" in event.structured_output:
                            iter_num += 1
                            yield _sse(
                                {
                                    "type": "executor_done",
                                    "iteration": iter_num,
                                    "report": event.structured_output.get(
                                        "report",
                                    ),
                                },
                            )
                            expecting_executor = False
                        elif "result" in event.structured_output:
                            result = event.structured_output.get("result")
                            yield _sse(
                                {
                                    "type": "verifier_done",
                                    "iteration": iter_num,
                                    "result": result,
                                    "message": event.structured_output.get(
                                        "message",
                                    ),
                                },
                            )
                            if result in ("pass", "impossible"):
                                final_status = result
                            expecting_executor = True
                elif isinstance(event, AgentEvent):
                    # Forward agent events as-is for live streaming
                    event_data = event.model_dump(mode="json")
                    event_data["iteration"] = iter_num if not expecting_executor else iter_num + 1
                    yield _sse(event_data)
        except Exception as exc:
            yield _sse(
                {"type": "error", "message": str(exc)},
            )
            return

        yield _sse(
            {
                "type": "pipeline_done",
                "final_status": final_status,
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
