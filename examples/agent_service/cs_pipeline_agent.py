# -*- coding: utf-8 -*-
"""Customer Service Agent with streaming pipeline.

This module defines :class:`CSPipelineAgent`, an :class:`Agent` subclass
that runs a 3-step streaming pipeline for every user message when the
agent's name is ``"Customer Service Agent"``:

1. **Analyze** — classifies the question (type, urgency, sentiment)
2. **Solve** — provides a solution based on the analysis
3. **Review** — reviews the solution and outputs the final response

All three steps stream their text deltas to the user in real time,
following the pipeline philosophy: "Every event from every agent inside
leaves through the same ``reply_stream``."

Each step gets its own ``TextBlock`` so the UI can render step labels
("Analyzing…", "Solving…", "Reviewing…") above the streaming text.

For all other agents, it delegates to the normal ``Agent._reply_impl``
with the same stuck-HITL recovery as :class:`RobustAgent`.

Usage in ``main.py``::

    from cs_pipeline_agent import CSPipelineAgent

    app = create_app(
        ...,
        custom_agent_cls=CSPipelineAgent,
    )
"""
from __future__ import annotations

import os
import time
from typing import AsyncGenerator, Type

from pydantic import BaseModel

from agentscope.agent import Agent
from agentscope.event import (
    AgentEvent,
    ExternalExecutionResultEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
    UserConfirmResultEvent,
    UserInterruptEvent,
)
from agentscope.message import Msg, UserMsg, AssistantMsg
from agentscope._logging import logger
from agentscope._utils._common import _generate_id
from agentscope.state import ReplyContext
from agentscope.types import ReplyFinishedReason


# ── Timing log ──────────────────────────────────────────────────────
# Writes per-step timing to a static file so we can analyse delays.
_TIMING_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "cs_pipeline_timing.log",
)


def _log_timing(message: str) -> None:
    """Append a timing line to the static log file.

    Args:
        message: The timing message to log.
    """
    try:
        with open(_TIMING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")
    except OSError:
        pass


# ── Sub-agent system prompts ─────────────────────────────────────────


_ANALYZER_PROMPT = (
    "You are a Customer Service Question Analyzer. Your job is to "
    "carefully read a customer's question and produce a structured "
    "analysis.\n\n"
    "Your analysis must include:\n"
    "1. **Question Type**: (e.g., product inquiry, complaint, "
    "technical support, billing, refund, shipping)\n"
    "2. **Urgency**: (low / medium / high / critical)\n"
    "3. **Complexity**: (simple / moderate / complex)\n"
    "4. **Key Information**: Extract the key facts and context\n"
    "5. **Sentiment**: (positive / neutral / frustrated / angry)\n"
    "6. **Suggested Approach**: Brief recommendation on how to "
    "handle this question\n\n"
    "Output only the structured analysis. Do not attempt to solve "
    "the problem — that is the next agent's job."
)

_SOLVER_PROMPT = (
    "You are a Customer Service Problem Solver. You receive a "
    "structured analysis of a customer's question (from the "
    "Question Analyzer) and must provide a clear, actionable "
    "solution.\n\n"
    "Your response must include:\n"
    "1. **Greeting**: Polite, personalized greeting\n"
    "2. **Acknowledgment**: Acknowledge the customer's concern\n"
    "3. **Solution**: Step-by-step solution or direct answer\n"
    "4. **Additional Resources**: Links, references, or next steps\n"
    "5. **Closing**: Professional closing with offer for further "
    "help\n\n"
    "Be concise but thorough. Use plain language. If the problem "
    "cannot be resolved without additional information, clearly "
    "state what is needed."
)

_REVIEWER_PROMPT = (
    "You are a Customer Service Response Reviewer. Your job is to "
    "review a proposed customer service response for quality "
    "before it is sent to the customer.\n\n"
    "Check for:\n"
    "1. **Accuracy**: Is the information correct?\n"
    "2. **Tone**: Is it polite, empathetic, and professional?\n"
    "3. **Completeness**: Does it fully address the customer's "
    "question?\n"
    "4. **Clarity**: Is it easy to understand?\n"
    "5. **Safety**: Does it avoid sensitive or inappropriate "
    "content?\n\n"
    "IMPORTANT: You must output the FULL final response that will "
    "be sent to the customer. If the proposed response is good, "
    "output it as-is. If it needs changes, output the corrected "
    "version. Do NOT output only a review note — output the "
    "complete customer-facing message."
)


# ── Pipeline agent ───────────────────────────────────────────────────


class CSPipelineAgent(Agent):
    """Agent that runs a 3-step streaming CS pipeline for each message.

    When the agent's name is ``"Customer Service Agent"``, each user
    message triggers three sub-agents internally:

    1. **Analyzer** — classifies and analyzes the question
    2. **Solver** — produces a draft response from the analysis
    3. **Reviewer** — reviews and finalises the response

    All three steps stream their text deltas to the user in real time.
    Each step gets its own ``TextBlock`` so the UI can show step labels.

    For all other agent names, this class delegates to the normal
    :meth:`Agent._reply_impl` with stuck-HITL recovery (same as
    :class:`RobustAgent`).
    """

    CS_AGENT_NAME = "Customer Service Agent"

    async def _reply_impl(  # pylint: disable=too-many-branches
        self,
        inputs: Msg
        | list[Msg]
        | UserConfirmResultEvent
        | UserInterruptEvent
        | ExternalExecutionResultEvent
        | None = None,
        structured_schema: Type[BaseModel] | None = None,
    ) -> AsyncGenerator[AgentEvent | Msg, None]:
        """Core reply logic.

        For the CS agent with a regular user message, run the streaming
        pipeline. For everything else, delegate to the parent with HITL
        recovery.
        """
        is_regular_message = isinstance(inputs, (Msg, list)) or inputs is None

        # Only run the pipeline for the CS agent on regular messages
        # (not HITL continuation events).
        if not (self.name == self.CS_AGENT_NAME and is_regular_message):
            async for item in self._delegate_to_parent(
                inputs, structured_schema,
            ):
                yield item
            return

        # ── Stuck-HITL recovery (same as RobustAgent) ──
        if self.state.has_awaiting_tool_calls(self.name):
            logger.info(
                "Abandoning pending tool calls from the previous "
                "interrupted reply to start a new one.",
            )
            async for evt in self._close_unfinished_tool_calls():
                yield evt

        # ── Handle incoming messages ──
        await self._handle_incoming_messages(inputs)

        # ── Set up reply context ──
        self.state.reply_context = ReplyContext(
            reply_id=_generate_id(),
            cur_iter=0,
            structured_schema=structured_schema,
            structured_output=None,
        )

        reply_id = self.state.reply_id
        _t_pipeline_start = time.monotonic()
        _log_timing(
            f"Pipeline START  reply_id={reply_id} "
            f"user_text={self._extract_user_text(inputs)[:80]!r}",
        )

        # ── Emit ReplyStartEvent ──
        yield ReplyStartEvent(
            session_id=self.state.session_id,
            reply_id=reply_id,
            name=self.name,
        )

        try:
            user_text = self._extract_user_text(inputs)

            # ── Step 1: Analyze (stream) ──
            _t_step1_start = time.monotonic()
            _log_timing(
                f"  Step 1 (Analyzer) START  "
                f"elapsed={_t_step1_start - _t_pipeline_start:.2f}s",
            )
            analysis_text = ""
            block_id_1 = _generate_id()
            yield TextBlockStartEvent(
                reply_id=reply_id,
                block_id=block_id_1,
            )
            # Emit step label so the user can see which step is running
            step1_label = "## 🔍 Step 1: Analyzing\n\n"
            analysis_text += step1_label
            yield TextBlockDeltaEvent(
                reply_id=reply_id,
                block_id=block_id_1,
                delta=step1_label,
            )
            async for event in self._run_step_stream(
                step_name="Analyzer",
                prompt=_ANALYZER_PROMPT,
                user_text=user_text,
                extra_context="",
            ):
                if isinstance(event, TextBlockDeltaEvent):
                    analysis_text += event.delta
                    yield TextBlockDeltaEvent(
                        reply_id=reply_id,
                        block_id=block_id_1,
                        delta=event.delta,
                    )
            yield TextBlockEndEvent(
                reply_id=reply_id,
                block_id=block_id_1,
            )
            _t_step1_end = time.monotonic()
            _log_timing(
                f"  Step 1 (Analyzer) DONE   "
                f"duration={_t_step1_end - _t_step1_start:.2f}s "
                f"total={_t_step1_end - _t_pipeline_start:.2f}s",
            )

            # ── Step 2: Solve (stream) ──
            _t_step2_start = time.monotonic()
            _log_timing(
                f"  Step 2 (Solver) START  "
                f"elapsed={_t_step2_start - _t_pipeline_start:.2f}s",
            )
            solver_text = ""
            block_id_2 = _generate_id()
            yield TextBlockStartEvent(
                reply_id=reply_id,
                block_id=block_id_2,
            )
            # Emit step label
            step2_label = "## 🔧 Step 2: Solving\n\n"
            solver_text += step2_label
            yield TextBlockDeltaEvent(
                reply_id=reply_id,
                block_id=block_id_2,
                delta=step2_label,
            )
            solver_extra = (
                f"Analysis from the Question Analyzer:\n"
                f"{analysis_text[len(step1_label):]}\n\n"
                f"Based on the analysis above, provide a clear, "
                f"actionable solution to the customer."
            )
            async for event in self._run_step_stream(
                step_name="Solver",
                prompt=_SOLVER_PROMPT,
                user_text=user_text,
                extra_context=solver_extra,
            ):
                if isinstance(event, TextBlockDeltaEvent):
                    solver_text += event.delta
                    yield TextBlockDeltaEvent(
                        reply_id=reply_id,
                        block_id=block_id_2,
                        delta=event.delta,
                    )
            yield TextBlockEndEvent(
                reply_id=reply_id,
                block_id=block_id_2,
            )
            _t_step2_end = time.monotonic()
            _log_timing(
                f"  Step 2 (Solver) DONE   "
                f"duration={_t_step2_end - _t_step2_start:.2f}s "
                f"total={_t_step2_end - _t_pipeline_start:.2f}s",
            )

            # ── Step 3: Review (stream) ──
            _t_step3_start = time.monotonic()
            _log_timing(
                f"  Step 3 (Reviewer) START  "
                f"elapsed={_t_step3_start - _t_pipeline_start:.2f}s",
            )
            final_text = ""
            block_id_3 = _generate_id()
            yield TextBlockStartEvent(
                reply_id=reply_id,
                block_id=block_id_3,
            )
            # Emit step label
            step3_label = "## ✅ Step 3: Final Response\n\n"
            final_text += step3_label
            yield TextBlockDeltaEvent(
                reply_id=reply_id,
                block_id=block_id_3,
                delta=step3_label,
            )
            reviewer_extra = (
                f"Proposed response to review:\n"
                f"{solver_text[len(step2_label):]}\n\n"
                f"Review the proposed response for accuracy, tone, "
                f"and completeness. Output the final response."
            )
            async for event in self._run_step_stream(
                step_name="Reviewer",
                prompt=_REVIEWER_PROMPT,
                user_text=user_text,
                extra_context=reviewer_extra,
            ):
                if isinstance(event, TextBlockDeltaEvent):
                    final_text += event.delta
                    yield TextBlockDeltaEvent(
                        reply_id=reply_id,
                        block_id=block_id_3,
                        delta=event.delta,
                    )
            yield TextBlockEndEvent(
                reply_id=reply_id,
                block_id=block_id_3,
            )
            _t_step3_end = time.monotonic()
            _log_timing(
                f"  Step 3 (Reviewer) DONE   "
                f"duration={_t_step3_end - _t_step3_start:.2f}s "
                f"total={_t_step3_end - _t_pipeline_start:.2f}s",
            )

            # ── Emit ReplyEndEvent ──
            _log_timing(
                f"Pipeline END    reply_id={reply_id} "
                f"total={time.monotonic() - _t_pipeline_start:.2f}s",
            )
            yield ReplyEndEvent(
                session_id=self.state.session_id,
                reply_id=reply_id,
                finished_reason=ReplyFinishedReason.COMPLETED,
            )

            # ── Emit final AssistantMsg ──
            yield AssistantMsg(
                id=reply_id,
                name=self.name,
                content=final_text or solver_text,
                finished_reason=ReplyFinishedReason.COMPLETED,
            )

        except Exception as exc:
            logger.exception(
                "CS pipeline failed for agent %r: %s",
                self.name,
                exc,
            )
            # Emit error reply end
            yield ReplyEndEvent(
                session_id=self.state.session_id,
                reply_id=reply_id,
                finished_reason=ReplyFinishedReason.ERROR,
            )
            yield AssistantMsg(
                id=reply_id,
                name=self.name,
                content=(
                    "I apologise — an internal error occurred while "
                    "processing your request. Please try again."
                ),
                finished_reason=ReplyFinishedReason.ERROR,
            )

    @staticmethod
    def _extract_user_text(
        inputs: Msg | list[Msg],
    ) -> str:
        """Extract the user's question text from the input message(s).

        Args:
            inputs: The user's input message(s).

        Returns:
            The concatenated user text.
        """
        if isinstance(inputs, list):
            return "\n".join(
                m.get_text_content() or "" for m in inputs
            )
        return inputs.get_text_content() or ""

    async def _run_step_stream(
        self,
        step_name: str,
        prompt: str,
        user_text: str,
        extra_context: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run one pipeline step as a sub-agent and stream its events.

        Creates a fresh sub-agent with the given system prompt, feeds it
        the user question (plus any extra context from previous steps),
        and yields all events from ``reply_stream``.

        Args:
            step_name: Display name for logging.
            prompt: System prompt for the sub-agent.
            user_text: The customer's original question.
            extra_context: Additional context from prior steps.

        Yields:
            Agent events from the sub-agent's ``reply_stream``.
        """
        sub_agent = Agent(
            name=f"CS {step_name}",
            system_prompt=prompt,
            model=self.model,
        )
        logger.info("[CS Pipeline] Step %s: streaming...", step_name)

        content_parts = [f"Customer's question:\n{user_text}"]
        if extra_context:
            content_parts.append(extra_context)

        sub_input = UserMsg(
            name="pipeline",
            content="\n\n".join(content_parts),
        )
        async for event in sub_agent.reply_stream(inputs=sub_input):
            yield event
        logger.info("[CS Pipeline] Step %s: done", step_name)

    async def _delegate_to_parent(
        self,
        inputs: Msg
        | list[Msg]
        | UserConfirmResultEvent
        | UserInterruptEvent
        | ExternalExecutionResultEvent
        | None,
        structured_schema: Type[BaseModel] | None,
    ) -> AsyncGenerator[AgentEvent | Msg, None]:
        """Delegate to the parent ``_reply_impl`` with HITL recovery.

        This generator is used for non-CS agents and for HITL
        continuation events.  It recovers from stuck HITL sessions
        before delegating, same as :class:`RobustAgent`.
        """
        is_regular_message = isinstance(inputs, (Msg, list)) or inputs is None
        if is_regular_message and self.state.has_awaiting_tool_calls(
            self.name,
        ):
            logger.info(
                "Abandoning pending tool calls from the previous "
                "interrupted reply to start a new one.",
            )
            async for evt in self._close_unfinished_tool_calls():
                yield evt

        async for item in super()._reply_impl(
            inputs=inputs,
            structured_schema=structured_schema,
        ):
            yield item
