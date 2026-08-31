# -*- coding: utf-8 -*-
"""Seed built-in agents on backend startup.

This module defines the inner (built-in) agents that should always be
available without manual setup.  Called from ``main.py`` during the
FastAPI startup event.

Usage in ``main.py``::

    from _seed_agents import seed_inner_agents

    @app.on_event("startup")
    async def _seed():
        await seed_inner_agents(storage, user_id="inner")
"""
from __future__ import annotations

from typing import Any

from agentscope._logging import logger
from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app.storage import AgentData, AgentRecord, StorageBase


# ── Inner agent definitions ──────────────────────────────────────────
# These are the canonical definitions for the built-in agents.
# ``setup_cs_agents.py`` imports this list for backward compatibility.


INNER_AGENTS: list[dict[str, Any]] = [
    # ── Customer Service Agent (main entry point) ──
    {
        "name": "Customer Service Agent",
        "system_prompt": (
            "You are a professional Customer Service Agent for a "
            "home-appliance company. You handle customer inquiries "
            "about orders, deliveries, refunds, product information, "
            "and technical support.\n\n"
            "Always be polite, empathetic, and solution-oriented. "
            "If you cannot resolve an issue directly, explain the "
            "next steps clearly."
        ),
    },
    # ── Pipeline sub-agents (used by the pipeline router) ──
    {
        "name": "CS Question Analyzer",
        "system_prompt": (
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
        ),
    },
    {
        "name": "CS Problem Solver",
        "system_prompt": (
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
        ),
    },
    {
        "name": "CS Response Reviewer",
        "system_prompt": (
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
            "If the response is acceptable, output it as the final "
            "response with a brief note: \"[REVIEWED] Response approved.\"\n"
            "If the response needs changes, output the corrected version "
            "with a note: \"[REVIEWED] Response revised: <reason>.\""
        ),
    },
    {
        "name": "CS Response Verifier",
        "system_prompt": (
            "You are a Customer Service Response Verifier. You evaluate "
            "whether a customer service response meets quality standards.\n\n"
            "Evaluate the response on:\n"
            "1. Does it directly address the customer's question?\n"
            "2. Is the tone appropriate (polite, empathetic)?\n"
            "3. Is the information accurate and complete?\n"
            "4. Does it offer further assistance?\n\n"
            "Respond with 'pass' if the response is acceptable, or 'fail' "
            "if it needs improvement, along with a brief explanation."
        ),
    },
]


async def seed_inner_agents(
    storage: StorageBase,
    user_id: str,
) -> None:
    """Create built-in agents if they don't already exist.

    Idempotent: safe to call on every startup.  Existing agents with
    the same name are left untouched.

    Args:
        storage (`StorageBase`):
            The storage backend to write agent records into.
        user_id (`str`):
            The user ID under which the inner agents are registered.
            Use a dedicated value (e.g. ``"inner"``) to keep built-in
            agents separate from real users' agents.
    """
    existing = await storage.list_agents(user_id)
    existing_names = {r.data.name for r in existing}

    created = 0
    for agent_def in INNER_AGENTS:
        name = agent_def["name"]
        if name in existing_names:
            logger.debug(
                "Inner agent %r already exists for user %r — skipping.",
                name,
                user_id,
            )
            continue

        data = AgentData(
            name=name,
            system_prompt=agent_def["system_prompt"],
            context_config=ContextConfig(),
            react_config=ReActConfig(),
        )
        record = AgentRecord(user_id=user_id, data=data)
        agent_id = await storage.upsert_agent(user_id, record)
        logger.info(
            "Seeded inner agent %r (id=%s) for user %r.",
            name,
            agent_id,
            user_id,
        )
        created += 1

    if created:
        logger.info(
            "Seeded %d inner agent(s) for user %r.",
            created,
            user_id,
        )
    else:
        logger.debug(
            "All %d inner agent(s) already exist for user %r.",
            len(INNER_AGENTS),
            user_id,
        )
