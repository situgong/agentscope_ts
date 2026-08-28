# Change Doc — Customer Service Pipeline Agent

**Date**: 2026-08-28
**Feature**: CS Agent with internal pipeline (check → solve → review)
**Complexity**: S (Simple)

---

## Goal

Make the "Customer Service Agent" run a 3-step internal pipeline for every
user message in a chat session:

1. **Analyze** — CS Question Analyzer classifies the question
2. **Solve** — CS Problem Solver provides a solution based on the analysis
3. **Review** — CS Response Reviewer reviews and outputs the final response

The user chats with the "Customer Service Agent" in the normal chat UI.
Each user message triggers the pipeline internally. The user sees the
final reviewed response streamed back.

## Implementation Approach

Create a new `CSPipelineAgent(Agent)` subclass that overrides
`_reply_impl`. For each user message:

1. Emit `ReplyStartEvent` (required by chat service)
2. Handle incoming messages (append to context)
3. Create 3 sub-agents (Analyzer, Solver, Reviewer) using `self.model`
4. Run sub-agent 1 (Analyzer) with the user's message → get analysis
5. Run sub-agent 2 (Solver) with the analysis → get draft response
6. Run sub-agent 3 (Reviewer) with the draft → get final response
7. Stream the final response as `TextBlockStart/Delta/End` events
8. Emit `ReplyEndEvent` + final `AssistantMsg`

Sub-agents are plain `Agent` instances created with the same model as
the parent agent. They use `reply()` (non-streaming) for intermediate
steps. Only the final reviewed response is streamed to the UI.

## Files

| File | Action | Description |
|---|---|---|
| `examples/agent_service/cs_pipeline_agent.py` | NEW | `CSPipelineAgent` class |
| `examples/agent_service/main.py` | MODIFY | Change `custom_agent_cls` to `CSPipelineAgent` |

## Impact

- No framework source code modified
- No frontend changes needed
- No DB/schema changes
- No new API endpoints

## Agent Detection

The `CSPipelineAgent` checks `self.name`. If the agent's name is
`"Customer Service Agent"`, it runs the pipeline. For all other agents,
it delegates to the normal `Agent._reply_impl` (via `super()`), preserving
the `RobustAgent` HITL recovery behavior.
