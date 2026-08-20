# -*- coding: utf-8 -*-
"""Custom pipeline router for the example agent service.

This router implements a **per-step instruction pipeline**: each agent
in the chain receives its own instruction message combined with the
previous agent's output. This replaces the V1 "workflow" concept where
users could give each step a different prompt.

The router is registered in ``main.py`` via ``app.include_router()``
after ``create_app()`` returns — no core agentscope code is modified.

.. note::

    Pipeline runs are **stateless**: each agent is assembled fresh from
    its stored config without session state, workspace tools, or
    middlewares.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agentscope.agent import Agent
from agentscope.app._service import ResourceAccessService
from agentscope.app.deps import get_current_user_id, get_resource_access_service
from agentscope.app._service._model import get_model
from agentscope.message import Msg, UserMsg, TextBlock

pipeline_router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
    responses={404: {"description": "Not found"}},
)


# ── Schemas ────────────────────────────────────────────────────────────


class PipelineSubStep(BaseModel):
    """A sub-step within a pipeline step.

    Attributes:
        agent_id: The stored agent ID to run.
        instruction: The instruction text for this sub-step's agent.
    """

    agent_id: str = Field(
        ...,
        description="The ID of the agent to run at this sub-step.",
    )
    instruction: str = Field(
        ...,
        description="The instruction for this sub-step's agent.",
    )


class PipelineStep(BaseModel):
    """One step in the pipeline.

    Attributes:
        agent_id: The stored agent ID to run.
        instruction: The instruction text for this agent. Combined with
            the previous step's output (if any) and sent to the agent.
        sub_steps: Optional sub-steps that run after the parent step.
            Each sub-step receives the parent step's output combined
            with its own instruction.
    """

    agent_id: str = Field(
        ...,
        description="The ID of the agent to run at this step.",
    )
    instruction: str = Field(
        ...,
        description=(
            "The instruction for this agent. For the first step, this "
            "is the sole input. For subsequent steps, it is combined "
            "with the previous agent's output."
        ),
    )
    sub_steps: list[PipelineSubStep] = Field(
        default_factory=list,
        description="Optional sub-steps executed after the parent step.",
    )


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
    reply: Msg = Field(..., description="The agent's reply message.")
    sub_results: list["PipelineStepResult"] = Field(
        default_factory=list,
        description="Results from sub-steps, if any.",
    )


# Resolve the forward reference in sub_results
PipelineStepResult.model_rebuild()


class RunPipelineResponse(BaseModel):
    """Response body for a pipeline run."""

    results: list[PipelineStepResult] = Field(
        ...,
        description="One result per step, in order.",
    )


# ── Agent assembly ─────────────────────────────────────────────────────


async def _assemble_agent(
    user_id: str,
    agent_id: str,
    chat_model_config: dict[str, Any],
    access: ResourceAccessService,
) -> Agent:
    """Assemble an :class:`Agent` from a stored agent record.

    Args:
        user_id: The caller's user ID.
        agent_id: The stored agent ID to load.
        chat_model_config: The chat model configuration dict.
        access: The resource access service.

    Returns:
        A ready-to-run agent instance.

    Raises:
        HTTPException: 404 if the agent is not found.
    """
    try:
        agent_record = await access.resolve_agent(user_id, agent_id)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id!r} not found.",
        ) from exc

    # Build the model from the config dict. We import ChatModelConfig
    # lazily to avoid importing storage at module level.
    from agentscope.app.storage import ChatModelConfig

    config = ChatModelConfig(**chat_model_config)
    model = await get_model(user_id, config, access)

    return Agent(
        name=agent_record.data.name,
        system_prompt=agent_record.data.system_prompt,
        model=model,
        context_config=agent_record.data.context_config,
        react_config=agent_record.data.react_config,
    )


# ── Endpoint ───────────────────────────────────────────────────────────


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

    For each step:
    - The agent is assembled from its stored config.
    - A ``UserMsg`` is created from the step's ``instruction``.
    - If there is a previous step, its text output is extracted and
      combined with the current instruction into a single ``UserMsg``,
      so the model sees the prior output as user-provided context
      rather than its own previous response.
    - The agent's reply is recorded and passed to the next step.

    Args:
        request: The pipeline request with steps and model config.
        user_id: Injected user ID.
        access: Injected resource access service.

    Returns:
        The results from each step.
    """
    results: list[PipelineStepResult] = []
    prev_reply: Msg | None = None

    for idx, step in enumerate(request.steps):
        agent = await _assemble_agent(
            user_id,
            step.agent_id,
            request.chat_model_config,
            access,
        )

        # Build the input: instruction + previous output (if any)
        instruction_msg = UserMsg(
            name="pipeline",
            content=step.instruction,
        )

        if prev_reply is not None:
            # Combine: previous agent's output + this step's instruction
            # We wrap the previous reply's text content into a user message
            # so the model always sees it as user-provided context, not as
            # its own previous response (which it would ignore).
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
            inputs = instruction_msg

        reply = await agent.reply(inputs)

        # Execute sub-steps: each receives the parent step's output
        sub_results: list[PipelineStepResult] = []
        current_reply = reply
        for sub_idx, sub_step in enumerate(step.sub_steps):
            sub_agent = await _assemble_agent(
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

        results.append(
            PipelineStepResult(
                step_index=idx,
                agent_id=step.agent_id,
                agent_name=agent.name,
                instruction=step.instruction,
                reply=reply,
                sub_results=sub_results,
            ),
        )

        # The last sub-step's output (or the parent's if no sub-steps)
        # becomes the input for the next parent step.
        prev_reply = current_reply

    return RunPipelineResponse(results=results)
