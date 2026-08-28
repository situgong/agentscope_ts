# -*- coding: utf-8 -*-
"""Custom Agent subclass that gracefully handles stuck HITL sessions.

When a session has pending HITL tool calls (ASKING or SUBMITTED state)
from a previous interrupted reply, and the user sends a new regular
message instead of a confirmation event, the base ``Agent._reply_impl``
raises ``ValueError`` because ``_check_incoming_event`` expects an
event but receives ``None``.  This ValueError is then misclassified as
a SETUP error by the chat service, showing the user a misleading
"check the agent's model, tools and knowledge bases" message.

This subclass overrides ``_reply_impl`` to intercept that situation:
before calling the original logic, it checks for pending tool calls
and closes them via ``_close_unfinished_tool_calls`` so the new reply
starts cleanly.

Usage in ``main.py``::

    from custom_agent import RobustAgent

    app = create_app(
        ...,
        custom_agent_cls=RobustAgent,
    )
"""
from typing import AsyncGenerator, Type

from pydantic import BaseModel

from agentscope.agent import Agent
from agentscope.event import (
    AgentEvent,
    UserConfirmResultEvent,
    UserInterruptEvent,
    ExternalExecutionResultEvent,
)
from agentscope.message import Msg
from agentscope._logging import logger


class RobustAgent(Agent):
    """Agent subclass that abandons pending HITL tool calls when the
    user sends a new message instead of confirming them."""

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
        """Core reply logic with stuck-HITL recovery.

        If the agent has pending tool calls from a previous interrupted
        reply (e.g. the user sent a new message instead of confirming a
        HITL tool call), close them first so the new reply starts
        cleanly.  Then delegate to the parent implementation.
        """
        # Only intercept regular messages (not HITL events or
        # interrupts).  When the input is a Msg/list[Msg] and the agent
        # is parked on awaiting tool calls, close them first.
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

        # Delegate to the original reply logic.
        async for item in super()._reply_impl(
            inputs=inputs,
            structured_schema=structured_schema,
        ):
            yield item
