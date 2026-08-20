# -*- coding: utf-8 -*-
"""The A2UI tool that lets agents emit declarative UI surfaces.

This is an example custom tool that extends AgentScope. It is
registered via ``create_app(extra_agent_tools=...)`` in ``main.py``.

Agents call this tool with A2UI v0.9.1 messages (createSurface,
updateComponents, updateDataModel, deleteSurface). The tool encodes
the messages as JSON Lines in a ``DataBlock`` with
``media_type="application/a2ui+json"``, which streams through the
existing SSE pipeline and is rendered by the ``@a2ui/react`` renderer
on the frontend.
"""
import base64
import json
from typing import Any, List

from agentscope.tool import ToolBase, ToolMiddlewareBase
from agentscope.tool._response import ToolChunk
from agentscope.message import DataBlock, Base64Source, TextBlock, ToolResultState
from agentscope.permission import (
    PermissionContext,
    PermissionDecision,
    PermissionBehavior,
)


class A2UI(ToolBase):
    """Emit an A2UI surface that renders as a rich, interactive UI in the
    web frontend.

    Call this tool with a list of A2UI v0.9.1 messages. Each message
    is a JSON object with a ``version`` field set to ``"v0.9.1"`` and
    exactly one of these top-level keys:

    - ``createSurface``: ``{surfaceId, catalogId}`` — initialise a
      new rendering surface. ``catalogId`` should be
      ``"basic"`` to use the built-in component catalog.
    - ``updateComponents``: ``{surfaceId, components: [...]}`` —
      add or replace components in the surface. Each component is
      ``{component: "Text", id: "txt-1", text: "Hello"}``.
      The root component MUST have ``id: "root"``.
    - ``updateDataModel``: ``{surfaceId, path?, value}`` — set data
      that components reference via ``{path: "/key"}`` bindings.
    - ``deleteSurface``: ``{surfaceId}`` — remove a surface.

    Component property reference:

    - **Text**: ``text`` (string or ``{path: "/key"}``),
      ``variant`` ("h1"/"h2"/"h3"/"h4"/"h5"/"caption"/"body")
    - **Button**: ``child`` (component ID for label),
      ``action`` (``{event: {name, context}}`` — always include
      so clicks are sent back to the agent),
      ``variant`` ("default"/"primary"/"borderless")
    - **Column**: ``children`` (array of component IDs),
      ``justify``, ``align``
    - **Row**: ``children`` (array of component IDs)
    - **Card**: ``child`` (single component ID)
    - **TextField**: ``label``, ``value`` (or ``{path}``),
      ``placeholder``
    - **CheckBox**: ``label``, ``isChecked`` (or ``{path}``)
    - **Image**: ``url`` (string or ``{path}``), ``description``
    - **Divider**: no required props
    - **Slider**: ``value`` (or ``{path}``), ``min``, ``max``, ``step``

    Example — a simple greeting card::

        messages = [
            {"version": "v0.9.1", "createSurface": {
                "surfaceId": "greeting", "catalogId": "basic"}},
            {"version": "v0.9.1", "updateComponents": {
                "surfaceId": "greeting",
                "components": [
                    {"component": "Card", "id": "root", "child": "col-1"},
                    {"component": "Column", "id": "col-1",
                     "children": ["title", "body"]},
                    {"component": "Text", "id": "title",
                     "text": {"path": "/title"},
                     "variant": "h2"},
                    {"component": "Text", "id": "body",
                     "text": {"path": "/body"}},
                ]}},
            {"version": "v0.9.1", "updateDataModel": {
                "surfaceId": "greeting", "path": "/",
                "value": {"title": "Hello!", "body": "from A2UI"}}},
        ]
    """

    name: str = "A2UI"
    """The tool name presented to the agent."""

    # pylint: disable=line-too-long
    description: str = """Render a rich, interactive UI surface using the A2UI protocol. Call this tool with a list of A2UI v0.9.1 messages to create surfaces, add components, set data, and delete surfaces.

Each message is a JSON object with "version": "v0.9.1" and one of:
- createSurface: {surfaceId, catalogId} — create a new surface (catalogId="basic")
- updateComponents: {surfaceId, components: [...]} — add/replace components
- updateDataModel: {surfaceId, path?, value} — set data for path bindings
- deleteSurface: {surfaceId} — remove a surface

Components use an adjacency-list model: each component has an "id" and references children by id. The ROOT component MUST have id="root". Available component types: Text, Image, Icon, Video, AudioPlayer, Row, Column, List, Card, Tabs, Divider, Modal, Button, TextField, CheckBox, ChoicePicker, Slider, DateTimeInput.

Key component properties:
- Text: text (plain string or {path: "/key"}), variant ("h1"/"h2"/"h3"/"h4"/"h5"/"caption"/"body")
- Button: child (component ID for label text), action ({event: {name, context}}), variant ("default"/"primary"/"borderless"). ALWAYS include an "action" with a unique event "name" so button clicks are sent back to you.
- Column: children (array of component IDs), justify, align
- Row: children (array of component IDs)
- Card: child (single component ID)
- TextField: label, value (or {path}), placeholder
- CheckBox: label, isChecked (or {path})
- Image: url (string or {path}), description
- Divider: no required props
- Slider: value (or {path}), min, max, step

Example:
  messages=[{"version":"v0.9.1","createSurface":{"surfaceId":"s1","catalogId":"basic"}},{"version":"v0.9.1","updateComponents":{"surfaceId":"s1","components":[{"component":"Column","id":"root","children":["t1","b1"]},{"component":"Text","id":"t1","text":"Hello A2UI!"},{"component":"Button","id":"b1","child":"btn-label","action":{"event":{"name":"click_me","context":{}}}},{"component":"Text","id":"btn-label","text":"Click Me"}]}}]
"""  # noqa: E501
    """The description presented to the agent."""

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "description": (
                    "A list of A2UI v0.9.1 messages to process. Each "
                    "message creates a surface, updates components, "
                    "updates the data model, or deletes a surface."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "string",
                            "const": "v0.9.1",
                        },
                    },
                    "required": ["version"],
                },
            },
        },
        "required": ["messages"],
    }

    is_mcp: bool = False
    is_read_only: bool = True
    is_concurrency_safe: bool = True
    is_external_tool: bool = False
    is_state_injected: bool = False

    def __init__(
        self,
        middlewares: List[ToolMiddlewareBase] | None = None,
    ) -> None:
        """Initialize the A2UI tool.

        Args:
            middlewares (`List[ToolMiddlewareBase] | None`, optional):
                Optional tool middlewares. Defaults to ``None``.
        """
        super().__init__(middlewares=middlewares)

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Check permissions for the A2UI tool.

        A2UI is a read-only tool: it only emits UI rendering
        instructions and never modifies files, processes, or external
        state. In EXPLORE mode the engine already handles the ALLOW via
        ``_check_explore_mode``, so here we just return PASSTHROUGH to
        let the engine continue with rule matching.

        Args:
            tool_input (`dict[str, Any]`):
                The tool input data (contains ``messages``).
            context (`PermissionContext`):
                The permission context for this invocation.

        Returns:
            `PermissionDecision`:
                PASSTHROUGH — A2UI is read-only.
        """
        return PermissionDecision(
            behavior=PermissionBehavior.PASSTHROUGH,
            message="A2UI is read-only.",
        )

    async def call(self, **kwargs: Any) -> ToolChunk:
        """Execute the A2UI tool.

        Args:
            messages (`list[dict]`):
                A list of A2UI v0.9.1 messages.

        Returns:
            `ToolChunk`:
                A tool chunk containing a DataBlock with the A2UI
                JSON Lines encoded as base64.
        """
        messages: list[dict] = kwargs.get("messages", [])

        if not messages:
            return ToolChunk(
                content=[
                    TextBlock(
                        text="A2UI: no messages provided.",
                    ),
                ],
                state=ToolResultState.ERROR,
            )

        # Encode messages as JSON Lines, then base64
        jsonl = "\n".join(
            json.dumps(msg, ensure_ascii=False) for msg in messages
        )
        encoded = base64.b64encode(jsonl.encode("utf-8")).decode("ascii")

        return ToolChunk(
            content=[
                DataBlock(
                    source=Base64Source(
                        data=encoded,
                        media_type="application/a2ui+json",
                    ),
                    name="a2ui-surface",
                ),
            ],
            state=ToolResultState.SUCCESS,
            metadata={"a2ui_message_count": len(messages)},
        )
