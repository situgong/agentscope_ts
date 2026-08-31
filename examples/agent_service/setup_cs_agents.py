# -*- coding: utf-8 -*-
"""Create customer service agents via the HTTP API (development utility).

.. deprecated::
    Agents are now seeded automatically on backend startup via
    :func:`_seed_agents.seed_inner_agents`.  This script is kept as a
    convenience for re-creating agents against a running server without
    restarting it, or for seeding under a different user ID.

Creates the 4 pipeline sub-agents via the AgentScope agent API:

1. CS Question Analyzer  — Sequential Step 1: classify & analyze questions
2. CS Problem Solver     — Sequential Step 2: solve the problem
3. CS Response Reviewer  — Sequential Step 3: review the response
4. CS Response Verifier  — Goal Verifier: verify response quality

Usage::

    python setup_cs_agents.py

    # Custom base URL or user ID
    python setup_cs_agents.py --base-url http://localhost:8000 --user-id default_user

Prerequisites:
    - The agent service must be running (default: http://localhost:8000)
    - The ``requests`` library must be installed
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

# Reuse the canonical agent definitions so there is a single source of
# truth — the list in ``_seed_agents.py`` is what the backend itself
# uses at startup.
from _seed_agents import INNER_AGENTS

# ``INNER_AGENTS`` includes the "Customer Service Agent" entry point,
# but this script only creates the 4 pipeline sub-agents (the main
# agent is expected to already exist or be auto-seeded by the backend).
AGENTS: list[dict[str, Any]] = [
    a for a in INNER_AGENTS if a["name"] != "Customer Service Agent"
]


# ── API helpers ───────────────────────────────────────────────────────


def create_agent(
    base_url: str,
    user_id: str,
    name: str,
    system_prompt: str,
) -> str:
    """Create an agent via the POST /agent/ endpoint.

    Args:
        base_url: The agent service base URL.
        user_id: The user ID for the X-User-ID header.
        name: The agent's display name.
        system_prompt: The agent's system prompt.

    Returns:
        The created agent's ID.

    Raises:
        RuntimeError: If the API call fails.
    """
    resp = requests.post(
        f"{base_url}/agent/",
        headers={
            "X-User-ID": user_id,
            "Content-Type": "application/json",
        },
        json={
            "name": name,
            "system_prompt": system_prompt,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["agent_id"]


def list_agents(base_url: str, user_id: str) -> list[dict[str, Any]]:
    """List all agents for a user.

    Args:
        base_url: The agent service base URL.
        user_id: The user ID for the X-User-ID header.

    Returns:
        A list of agent dicts with ``id`` and ``data.name`` keys.
    """
    resp = requests.get(
        f"{base_url}/agent/",
        headers={"X-User-ID": user_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["agents"]


def find_agent_by_name(
    agents: list[dict[str, Any]],
    name: str,
) -> dict[str, Any] | None:
    """Find an agent by name.

    Args:
        agents: The list of agents.
        name: The name to search for.

    Returns:
        The agent dict, or ``None`` if not found.
    """
    for agent in agents:
        if agent["data"]["name"] == name:
            return agent
    return None


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    """Create the 4 customer service agents if they don't exist."""
    parser = argparse.ArgumentParser(
        description="Create customer service pipeline agents.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Agent service base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--user-id",
        default="default_user",
        help="User ID for X-User-ID header (default: default_user)",
    )
    args = parser.parse_args()

    # Check existing agents to avoid duplicates
    existing = list_agents(args.base_url, args.user_id)
    print(f"Found {len(existing)} existing agent(s):")
    for a in existing:
        print(f"  - {a['data']['name']} ({a['id']})")

    created: list[tuple[str, str]] = []

    for agent_def in AGENTS:
        name = agent_def["name"]
        prompt = agent_def["system_prompt"]

        # Skip if already exists
        if find_agent_by_name(existing, name):
            agent = find_agent_by_name(existing, name)
            print(f"\n  [SKIP] '{name}' already exists (ID: {agent['id']})")
            created.append((name, agent["id"]))
            continue

        # Create the agent
        try:
            agent_id = create_agent(
                args.base_url,
                args.user_id,
                name,
                prompt,
            )
            print(f"\n  [OK]   Created '{name}' (ID: {agent_id})")
            created.append((name, agent_id))
        except Exception as exc:
            print(f"\n  [FAIL] Failed to create '{name}': {exc}")
            sys.exit(1)

    # Print pipeline configuration summary
    print("\n" + "=" * 60)
    print("Pipeline Configuration Summary")
    print("=" * 60)

    name_to_id = {name: aid for name, aid in created}

    # Also find the existing Customer Service Agent
    cs_agent = find_agent_by_name(existing, "Customer Service Agent")
    cs_agent_id = cs_agent["id"] if cs_agent else "???"
    if not cs_agent:
        # Try to find it among newly created (unlikely, but just in case)
        cs_agent_id = name_to_id.get("Customer Service Agent", "???")

    print("\nPipeline 1 — Sequential (Check → Solve → Review)")
    print("-" * 60)
    print(f"  Step 1 (Analyze):  CS Question Analyzer  → {name_to_id.get('CS Question Analyzer', '???')}")
    print(f"  Step 2 (Solve):    CS Problem Solver     → {name_to_id.get('CS Problem Solver', '???')}")
    print(f"  Step 3 (Review):   CS Response Reviewer  → {name_to_id.get('CS Response Reviewer', '???')}")
    print("\n  Instructions:")
    print('    Step 1: "Analyze this customer question: classify type,')
    print('             urgency, complexity, and sentiment."')
    print('    Step 2: "Based on the analysis above, provide a clear,')
    print('             actionable solution to the customer."')
    print('    Step 3: "Review the proposed solution for accuracy, tone,')
    print('             and completeness. Output the final response."')

    print("\nPipeline 2 — Goal (Executor + Verifier)")
    print("-" * 60)
    print(f"  Executor: Customer Service Agent → {cs_agent_id}")
    print(f"  Verifier: CS Response Verifier   → {name_to_id.get('CS Response Verifier', '???')}")
    print(f"  Max Iters: 5")
    print('\n  Instruction: "Handle the customer\'s request and provide')
    print('               a professional response."')

    print("\n" + "=" * 60)
    print("Done! Select these agents in the Pipeline page to run the pipelines.")
    print("=" * 60)


if __name__ == "__main__":
    main()
