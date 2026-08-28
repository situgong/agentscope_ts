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

# ─── A2UI v0.9 Schema Mirror ─────────────────────────────────────────────────
# These rules mirror the Zod schemas in @a2ui/web_core v0_9/basic_catalog.
# They are used to validate/fix agent-generated messages BEFORE encoding,
# so the agent gets actionable error feedback instead of a silent render
# failure on the frontend.

# Properties that each component type accepts (beyond the common ones).
# "strict" means unknown keys will be stripped.
# Common properties (all components): id, accessibility, weight
# Mirrors the Zod strict-mode schemas in @a2ui/web_core v0_9/basic_catalog.
_COMPONENT_SCHEMAS: dict[str, set[str]] = {
    "Text": {"text", "variant"},
    "Image": {"url", "description", "fit", "variant"},
    "Icon": {"name"},
    "Video": {"url"},
    "AudioPlayer": {"url", "description"},
    "Row": {"children", "justify", "align"},
    "Column": {"children", "justify", "align"},
    "List": {"children", "direction", "align", "listStyle"},
    "Card": {"child"},
    "Tabs": {"tabs"},
    "Divider": {"axis"},
    "Modal": {"trigger", "content"},
    "Button": {
        "child", "action", "variant", "checks", "isValid",
        "validationErrors",
    },
    "TextField": {
        "label", "value", "variant", "validationRegexp", "checks",
        "isValid", "validationErrors",
    },
    "CheckBox": {
        "label", "value", "checks", "isValid", "validationErrors",
    },
    "ChoicePicker": {
        "label", "variant", "options", "value", "displayStyle",
        "filterable", "checks", "isValid", "validationErrors",
    },
    "Slider": {
        "value", "min", "max", "label", "checks", "isValid",
        "validationErrors",
    },
    "DateTimeInput": {
        "value", "enableDate", "enableTime", "min", "max", "label",
        "checks", "isValid", "validationErrors",
    },
}

# Required fields per component type (beyond id/component).
_COMPONENT_REQUIRED: dict[str, set[str]] = {
    "Text": {"text"},
    "Image": {"url"},
    "Icon": {"name"},
    "Video": {"url"},
    "AudioPlayer": {"url"},
    "Row": {"children"},
    "Column": {"children"},
    "List": {"children"},
    "Card": {"child"},
    "Tabs": {"tabs"},
    "Modal": {"trigger", "content"},
    "Button": {"child"},
    "TextField": {"label"},
    "CheckBox": {"label", "value"},
    "ChoicePicker": {"options", "value"},
    "Slider": {"value", "max"},
    "DateTimeInput": {"value"},
}

# Components that reference other component IDs.
# Maps component type → list of property names that hold ComponentId references.
# For Tabs, "tabs" is an array of {title, child} — the "child" in each
# item is a ComponentId reference.
_REF_FIELDS: dict[str, list[str]] = {
    "Row": ["children"],
    "Column": ["children"],
    "List": ["children"],
    "Card": ["child"],
    "Button": ["child"],
    "Modal": ["trigger", "content"],
    "Tabs": ["tabs"],
}


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

    Data binding: any string-type property can be either a literal
    string or a dynamic binding ``{"path": "/dataKey"}``. The value
    is resolved from the data model set via ``updateDataModel``.

    Actions: interactive components (Button) accept an ``action``
    property: ``{"event": {"name": "event_name", "context": {}}}``.
    When the user interacts, the event is sent back to the agent.

    Checks/validation: checkable components (Button, TextField,
    CheckBox, ChoicePicker, Slider, DateTimeInput) support
    ``checks`` (array of check definitions), ``isValid`` (bool),
    and ``validationErrors`` (array of strings).

    Component property reference (all components also accept
    ``id``, ``accessibility``, ``weight``):

    - **Text**: ``text`` (string or ``{path}``, **required**),
      ``variant`` ("h1"/"h2"/"h3"/"h4"/"h5"/"caption"/"body")
    - **Button**: ``child`` (component ID, **required**),
      ``action`` (``{event: {name, context}}`` — include so clicks
      are sent back to the agent),
      ``variant`` ("default"/"primary"/"borderless"),
      ``checks``, ``isValid``, ``validationErrors``
    - **Column**: ``children`` (array of component IDs,
      **required**), ``justify``, ``align``
    - **Row**: ``children`` (array of component IDs,
      **required**), ``justify``, ``align``
    - **List**: ``children`` (array of component IDs,
      **required**), ``direction``, ``align``, ``listStyle``
    - **Card**: ``child`` (single component ID, **required**)
    - **Tabs**: ``tabs`` (array of ``{title, child}``,
      **required** — ``child`` is a component ID reference)
    - **Modal**: ``trigger`` (component ID, **required**),
      ``content`` (component ID, **required**)
    - **TextField**: ``label`` (**required**), ``value``
      (or ``{path}``), ``variant``, ``validationRegexp``,
      ``checks``, ``isValid``, ``validationErrors``
    - **CheckBox**: ``label`` (**required**),
      ``value`` (DynamicBoolean or ``{path}``, **required**),
      ``checks``, ``isValid``, ``validationErrors``
    - **ChoicePicker**: ``options`` (array, **required**),
      ``value`` (**required**), ``label``, ``variant``,
      ``displayStyle``, ``filterable``,
      ``checks``, ``isValid``, ``validationErrors``
    - **Slider**: ``value`` (or ``{path}``, **required**),
      ``max`` (**required**), ``min``, ``label``,
      ``checks``, ``isValid``, ``validationErrors``
    - **DateTimeInput**: ``value`` (or ``{path}``,
      **required**), ``enableDate``, ``enableTime``,
      ``min``, ``max``, ``label``,
      ``checks``, ``isValid``, ``validationErrors``
    - **Image**: ``url`` (string or ``{path}``, **required**),
      ``description``, ``fit``, ``variant``
    - **Icon**: ``name`` (**required**)
    - **Video**: ``url`` (string or ``{path}``, **required**)
    - **AudioPlayer**: ``url`` (string or ``{path}``,
      **required**), ``description``
    - **Divider**: ``axis`` ("horizontal"/"vertical")

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
    description: str = """Render interactive UI surfaces using the A2UI v0.9.1 protocol. Call this tool with a list of JSON messages to create surfaces, add components, set data, and delete surfaces.

Read the "a2ui-generation" skill (via the Skill tool) for the full protocol specification, component reference, and examples before calling this tool.

Quick reference:
- Messages: createSurface {surfaceId, catalogId="basic"}, updateComponents {surfaceId, components}, updateDataModel {surfaceId, value}, deleteSurface {surfaceId}
- Components use ID references (adjacency-list model). One component MUST have id="root".
- 18 component types: Text, Image, Icon, Video, AudioPlayer, Row, Column, List, Card, Tabs, Divider, Modal, Button, TextField, CheckBox, ChoicePicker, Slider, DateTimeInput
- Data binding: {"path": "/key"} resolves from data model set via updateDataModel
- Actions: Button "action": {"event": {"name": "event_name", "context": {}}} — clicks sent back to you
- Validation: "checks" array on input components and buttons

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

        Validates the messages before encoding. If validation finds
        errors that cannot be auto-fixed, the tool returns an error
        result with actionable guidance so the agent can self-correct
        and retry.

        Args:
            messages (`list[dict]`):
                A list of A2UI v0.9.1 messages.

        Returns:
            `ToolChunk`:
                A tool chunk containing a DataBlock with the A2UI
                JSON Lines encoded as base64, or an error message.
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

        # Validate and auto-fix messages before encoding
        errors = self._validate_messages(messages)
        if errors:
            error_report = self._format_errors(errors)
            return ToolChunk(
                content=[
                    TextBlock(
                        text=(
                            "A2UI validation failed. Your messages "
                            "contain errors that would prevent the "
                            "surface from rendering. Please fix them "
                            "and call A2UI again.\n\n"
                            f"{error_report}"
                        ),
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

    @staticmethod
    def _validate_messages(
        messages: list[dict],
    ) -> list[str]:
        """Validate A2UI messages against the v0.9 schema.

        Auto-fixes what it can (strips unknown keys) and returns a
        list of error strings for issues that require the agent to
        regenerate the message.

        Args:
            messages (`list[dict]`):
                The A2UI messages to validate. Modified in-place.

        Returns:
            `list[str]`:
                List of error descriptions. Empty if all valid.
        """
        errors: list[str] = []

        # Track all component IDs and their types per surface
        # so we can check references.
        surface_components: dict[str, dict[str, str]] = {}
        # Track which surfaces have been explicitly created.
        created_surfaces: set[str] = set()

        for msg_idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                errors.append(
                    f"Message {msg_idx}: not a JSON object."
                )
                continue

            version = msg.get("version")
            if version != "v0.9.1":
                errors.append(
                    f"Message {msg_idx}: version must be "
                    f"'v0.9.1', got '{version}'."
                )

            # Check exactly one top-level key
            top_keys = {
                "createSurface", "updateComponents",
                "updateDataModel", "deleteSurface",
            }
            present = top_keys & set(msg.keys())
            if len(present) != 1:
                errors.append(
                    f"Message {msg_idx}: must have exactly one of "
                    f"createSurface/updateComponents/"
                    f"updateDataModel/deleteSurface, "
                    f"got {sorted(present)}."
                )
                continue

            key = present.pop()

            if key == "createSurface":
                cs = msg["createSurface"]
                if not isinstance(cs, dict):
                    errors.append(
                        f"Message {msg_idx}: createSurface must be "
                        f"an object."
                    )
                    continue
                sid = cs.get("surfaceId")
                if not sid:
                    errors.append(
                        f"Message {msg_idx}: createSurface requires "
                        f"'surfaceId'."
                    )
                created_surfaces.add(sid)
                surface_components.setdefault(sid, {})

            elif key == "updateComponents":
                uc = msg["updateComponents"]
                if not isinstance(uc, dict):
                    errors.append(
                        f"Message {msg_idx}: updateComponents must "
                        f"be an object."
                    )
                    continue
                sid = uc.get("surfaceId")
                comps = uc.get("components")
                if not isinstance(comps, list):
                    errors.append(
                        f"Message {msg_idx}: updateComponents "
                        f"requires 'components' array."
                    )
                    continue

                # Check that createSurface was sent first
                if sid not in created_surfaces:
                    errors.append(
                        f"Message {msg_idx}: updateComponents for "
                        f"surface '{sid}' sent before createSurface. "
                        f"You must createSurface first."
                    )
                    continue

                comp_map = surface_components.setdefault(sid, {})
                has_root = False

                for ci, comp in enumerate(comps):
                    if not isinstance(comp, dict):
                        errors.append(
                            f"Message {msg_idx}, component {ci}: "
                            f"not a JSON object."
                        )
                        continue

                    comp_type = comp.get("component")
                    comp_id = comp.get("id")

                    if not comp_type:
                        errors.append(
                            f"Message {msg_idx}, component {ci}: "
                            f"missing 'component' type."
                        )
                        continue
                    if not comp_id:
                        errors.append(
                            f"Message {msg_idx}, component {ci}: "
                            f"missing 'id'."
                        )
                        continue

                    if comp_id == "root":
                        has_root = True

                    comp_map[comp_id] = comp_type

                    # Check component type is known
                    if comp_type not in _COMPONENT_SCHEMAS:
                        errors.append(
                            f"Message {msg_idx}, component "
                            f"'{comp_id}': unknown component type "
                            f"'{comp_type}'. Valid types: "
                            f"{sorted(_COMPONENT_SCHEMAS.keys())}."
                        )
                        continue

                    # Check required fields
                    required = _COMPONENT_REQUIRED.get(comp_type, set())
                    for req in required:
                        if req not in comp:
                            errors.append(
                                f"Message {msg_idx}, component "
                                f"'{comp_id}' ({comp_type}): "
                                f"missing required property "
                                f"'{req}'."
                            )

                    # Strip unknown keys (strict mode).
                    # Common properties allowed on ALL components:
                    # id, component, weight, accessibility.
                    allowed = _COMPONENT_SCHEMAS[comp_type] | {
                        "component", "id", "weight", "accessibility",
                    }
                    unknown = set(comp.keys()) - allowed
                    for uk in unknown:
                        del comp[uk]

                    # Validate checks format: each check must have
                    # "condition" (a function call) and "message".
                    # Auto-fix the common mistake of putting call/args
                    # directly in the check object.
                    if "checks" in comp and isinstance(
                        comp["checks"], list
                    ):
                        for ci_check, check in enumerate(
                            comp["checks"]
                        ):
                            if not isinstance(check, dict):
                                continue
                            # Auto-fix: if check has "call" but no
                            # "condition", wrap it.
                            if "call" in check and "condition" not in check:
                                call_val = check.pop("call")
                                args_val = check.pop("args", {})
                                return_type = check.pop(
                                    "returnType", "boolean"
                                )
                                check["condition"] = {
                                    "call": call_val,
                                    "args": args_val,
                                    "returnType": return_type,
                                }
                            # Auto-fix: if condition exists but is
                            # missing returnType, add it (Zod schema
                            # requires returnType:"boolean" for
                            # DynamicBoolean function calls).
                            cond = check.get("condition")
                            if isinstance(cond, dict) and "call" in cond:
                                if "returnType" not in cond:
                                    cond["returnType"] = "boolean"
                                # Also fix nested function calls in
                                # args values (e.g. "and"/"or" with
                                # nested "required" calls).
                                args = cond.get("args", {})
                                if isinstance(args, dict):
                                    for v in args.values():
                                        if (
                                            isinstance(v, dict)
                                            and "call" in v
                                            and "returnType" not in v
                                        ):
                                            v["returnType"] = "boolean"
                            # Validate: condition is required
                            if "condition" not in check:
                                errors.append(
                                    f"Message {msg_idx}, component "
                                    f"'{comp_id}' ({comp_type}): "
                                    f"checks[{ci_check}] missing "
                                    f"'condition'. Each check must "
                                    f"have 'condition' (a function "
                                    f"call) and 'message'."
                                )

                if comps and not has_root:
                    errors.append(
                        f"Message {msg_idx}: updateComponents for "
                        f"surface '{sid}' has no component with "
                        f"id='root'. The root component is required."
                    )

            elif key == "updateDataModel":
                ud = msg["updateDataModel"]
                if not isinstance(ud, dict):
                    errors.append(
                        f"Message {msg_idx}: updateDataModel must "
                        f"be an object."
                    )
                    continue
                sid = ud.get("surfaceId")
                if sid and sid not in created_surfaces:
                    errors.append(
                        f"Message {msg_idx}: updateDataModel for "
                        f"surface '{sid}' sent before createSurface. "
                        f"You must createSurface first."
                    )
                if "value" not in ud:
                    errors.append(
                        f"Message {msg_idx}: updateDataModel "
                        f"requires 'value'."
                    )

            elif key == "deleteSurface":
                ds = msg["deleteSurface"]
                if not isinstance(ds, dict):
                    errors.append(
                        f"Message {msg_idx}: deleteSurface must "
                        f"be an object."
                    )
                    continue
                if not ds.get("surfaceId"):
                    errors.append(
                        f"Message {msg_idx}: deleteSurface "
                        f"requires 'surfaceId'."
                    )

        # Check component ID references
        for sid, comp_map in surface_components.items():
            for comp_id, comp_type in comp_map.items():
                ref_fields = _REF_FIELDS.get(comp_type, [])
                if not ref_fields:
                    continue
                # Re-scan messages to find the component dict
                for msg in messages:
                    uc = msg.get("updateComponents")
                    if not isinstance(uc, dict):
                        continue
                    if uc.get("surfaceId") != sid:
                        continue
                    for comp in uc.get("components", []):
                        if not isinstance(comp, dict):
                            continue
                        if comp.get("id") != comp_id:
                            continue
                        for field in ref_fields:
                            if field not in comp:
                                continue
                            val = comp[field]
                            # Tabs: "tabs" is an array of
                            # {title, child} where child is a
                            # ComponentId reference.
                            if comp_type == "Tabs":
                                if not isinstance(val, list):
                                    continue
                                for tab_item in val:
                                    if not isinstance(tab_item, dict):
                                        continue
                                    ref = tab_item.get("child")
                                    if (
                                        isinstance(ref, str)
                                        and ref not in comp_map
                                    ):
                                        errors.append(
                                            f"Component '{comp_id}' "
                                            f"(Tabs) references "
                                            f"'{ref}' in tabs[].child, "
                                            f"but no component with "
                                            f"id='{ref}' exists in "
                                            f"surface '{sid}'."
                                        )
                                continue
                            # Other ref fields: string or list of
                            # strings
                            refs = val
                            if isinstance(refs, str):
                                refs = [refs]
                            if isinstance(refs, list):
                                for ref in refs:
                                    if (
                                        isinstance(ref, str)
                                        and ref not in comp_map
                                    ):
                                        errors.append(
                                            f"Component '{comp_id}' "
                                            f"({comp_type}) references "
                                            f"'{ref}' in '{field}', "
                                            f"but no component with "
                                            f"id='{ref}' exists in "
                                            f"surface '{sid}'."
                                        )

        return errors

    @staticmethod
    def _format_errors(errors: list[str]) -> str:
        """Format validation errors for the agent.

        Args:
            errors (`list[str]`):
                The error strings from _validate_messages.

        Returns:
            `str`:
                A formatted error report.
        """
        lines = [f"Found {len(errors)} validation error(s):\n"]
        for i, err in enumerate(errors, 1):
            lines.append(f"  {i}. {err}")
        lines.append(
            "\nFix these issues and call the A2UI tool again with "
            "corrected messages."
        )
        return "\n".join(lines)
