# -*- coding: utf-8 -*-
"""Sequential pipeline that chains agents sequentially.

Each agent receives its instruction combined with the previous agent's
output. Implements :class:`~agentscope.pipeline.PipelineProtocol` so it
can be used wherever an ``Agent`` is expected.

This is the refactored version of the inline chain logic that previously
lived in ``pipeline_router.py``.  The router now delegates to this class,
keeping the HTTP layer thin.

.. note::

    Pipeline runs are **stateless**: each agent is assembled fresh from
    its stored config without session state, workspace tools, or
    middlewares.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

from agentscope.agent import Agent
from agentscope.app._service import ResourceAccessService
from agentscope.app._service._model import get_model
from agentscope.event import AgentEvent
from agentscope.message import Msg, UserMsg
from agentscope.pipeline import PipelineProtocol


# ── Schemas (shared with router) ──────────────────────────────────────


class PipelineSubStep(BaseModel):
    """A sub-step within a pipeline step.

    Args:
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

    Args:
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


# ── Agent assembly (shared utility) ───────────────────────────────────


async def assemble_agent(
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
        Exception: If the agent is not found or model creation fails.
    """
    from fastapi import HTTPException, status

    try:
        agent_record = await access.resolve_agent(user_id, agent_id)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id!r} not found.",
        ) from exc

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


# ── SequentialPipeline ────────────────────────────────────────────────


class SequentialPipeline:
    """A pipeline that chains agents sequentially.

    Each agent receives its instruction combined with the previous
    agent's output.  Optional sub-steps run after each parent step,
    and the parent re-runs with the combined sub-step outputs to
    produce a consolidated result.

    Implements :class:`~agentscope.pipeline.PipelineProtocol` so it
    can be used wherever an ``Agent`` is expected (e.g.
    ``launch_console``).

    Args:
        steps: The ordered pipeline steps.
        chat_model_config: The chat model configuration dict (as
            ``ChatModelConfig`` serialised).  Shared by all agents.
        user_id: The caller's user ID.
        access: The resource access service.
    """

    def __init__(
        self,
        steps: list[PipelineStep],
        chat_model_config: dict[str, Any],
        user_id: str,
        access: ResourceAccessService,
    ) -> None:
        self.steps = steps
        self.chat_model_config = chat_model_config
        self.user_id = user_id
        self.access = access

    async def reply_stream(
        self,
        inputs: Msg | list[Msg],
    ) -> AsyncGenerator[AgentEvent | Msg, None]:
        """Run the sequential pipeline.

        Args:
            inputs: The initial input message.  For the first step,
                the step's instruction is used instead.

        Yields:
            ``AgentEvent`` or ``Msg``: Events from each agent's
            ``reply_stream()``, plus ``Msg`` objects for each step's
            final reply.
        """
        prev_reply: Msg | None = None

        for idx, step in enumerate(self.steps):
            agent = await assemble_agent(
                self.user_id,
                step.agent_id,
                self.chat_model_config,
                self.access,
            )

            # Build the input: instruction + previous output (if any)
            if prev_reply is not None:
                prev_text = prev_reply.get_text_content() or ""
                combined_instruction = (
                    f"Previous step output:\n{prev_text}\n\n"
                    f"Your instruction:\n{step.instruction}"
                )
                step_inputs: Msg | list[Msg] = UserMsg(
                    name="pipeline",
                    content=combined_instruction,
                )
            else:
                step_inputs = UserMsg(
                    name="pipeline",
                    content=step.instruction,
                )

            # Run the agent and stream events
            reply: Msg | None = None
            async for event in agent.reply_stream(inputs=step_inputs):
                yield event
                if isinstance(event, Msg) and event.finished_reason:
                    reply = event

            if reply is None:
                # Fallback: call reply() directly if no final Msg
                reply = await agent.reply(step_inputs)

            # Execute sub-steps
            current_reply = reply
            sub_replies: list[Msg] = []
            for sub_step in step.sub_steps:
                sub_agent = await assemble_agent(
                    self.user_id,
                    sub_step.agent_id,
                    self.chat_model_config,
                    self.access,
                )
                parent_text = current_reply.get_text_content() or ""
                sub_combined = (
                    f"Previous output:\n{parent_text}\n\n"
                    f"Your instruction:\n{sub_step.instruction}"
                )
                sub_inputs = UserMsg(
                    name="pipeline",
                    content=sub_combined,
                )
                sub_reply: Msg | None = None
                async for event in sub_agent.reply_stream(inputs=sub_inputs):
                    yield event
                    if isinstance(event, Msg) and event.finished_reason:
                        sub_reply = event
                if sub_reply is None:
                    sub_reply = await sub_agent.reply(sub_inputs)
                sub_replies.append(sub_reply)
                current_reply = sub_reply

            # If there were sub-steps, re-run the parent agent with
            # the sub-step outputs to consolidate.
            if step.sub_steps:
                sub_outputs = "\n\n".join(
                    f"Sub-step {i + 1} output:\n"
                    f"{sr.get_text_content() or ''}"
                    for i, sr in enumerate(sub_replies)
                )
                final_instruction = (
                    f"Your initial output:\n"
                    f"{reply.get_text_content() or ''}\n\n"
                    f"Sub-step outputs:\n{sub_outputs}\n\n"
                    f"Please consolidate the above into a final "
                    f"response based on your original instruction:\n"
                    f"{step.instruction}"
                )
                final_inputs = UserMsg(
                    name="pipeline",
                    content=final_instruction,
                )
                final_reply: Msg | None = None
                async for event in agent.reply_stream(inputs=final_inputs):
                    yield event
                    if isinstance(event, Msg) and event.finished_reason:
                        final_reply = event
                if final_reply is None:
                    final_reply = await agent.reply(final_inputs)
                current_reply = final_reply

            prev_reply = current_reply
