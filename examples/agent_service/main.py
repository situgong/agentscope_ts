# -*- coding: utf-8 -*-
"""The example script to start the agent service."""
import os
import sys

# Windows asyncio needs the ProactorEventLoop to support subprocesses
# (create_subprocess_exec). The default SelectorEventLoop raises
# NotImplementedError, which breaks workspace/skill listing and other
# shell-based operations.
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from agentscope.app import create_app, SubAgentTemplate
from agentscope.app.channel import (
    DingTalkChannel,
    DiscordChannel,
    FeishuChannel,
)

# Custom Agent subclass that runs a 3-step CS pipeline (analyze → solve
# → review) for the "Customer Service Agent", and recovers from stuck
# HITL sessions for all other agents.
from cs_pipeline_agent import CSPipelineAgent

# Built-in agent definitions + startup seeder
from _seed_agents import seed_inner_agents
from agentscope.app.hub import ClawSkillHub, GitHubMCPHub
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager
from agentscope.app.storage import RedisStorage
from auto_cleanup_workspace_manager import AutoCleanupDockerWorkspaceManager
from agentscope.mcp import MCPClient, StdioMCPConfig, HttpMCPConfig
from agentscope.middleware import AgenticMemoryMiddleware, MiddlewareBase
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.rag import ApproxTokenChunker, QdrantStore
from agentscope.tool import ToolBase
from agentscope.workspace import WorkspaceBase

# No default MCPs — each agent loads only the tools/MCPs it needs.
# The previous "browser-use" (Playwright) MCP took ~72s to connect
# on every chat run, which delayed the first token by that much.
# Agents that need browser tools can add the MCP via the UI.
default_mcps = []

if os.getenv("AMAP_API_KEY"):
    default_mcps.append(
        MCPClient(
            name="amap",
            mcp_config=HttpMCPConfig(
                url=f"https://mcp.amap.com/mcp?key="
                f"{os.environ['AMAP_API_KEY']}",
            ),
            is_stateful=False,
        ),
    )

storage = RedisStorage(
    host="localhost",
    port=6379,
)

vector_store = QdrantStore(location=":memory:")


async def longterm_memory_factory(
    user_id: str,
    agent_id: str,
    session_id: str,
    workspace: WorkspaceBase,
) -> list[MiddlewareBase]:
    """Attach Markdown-file long-term memory, stored under the session's
    workspace so it is reachable through whichever backend is bound."""
    del user_id, agent_id, session_id
    return [
        AgenticMemoryMiddleware(
            workdir=workspace.workdir,
            backend=workspace.get_backend(),
        ),
    ]


async def a2ui_tool_factory(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    """Register the A2UI custom tool so agents can emit declarative UI
    surfaces rendered by the ``@a2ui/react`` frontend."""
    del user_id, agent_id, session_id
    from a2ui_tool import A2UI

    return [A2UI()]


app = create_app(
    storage=storage,
    message_bus=InMemoryMessageBus(),
    # -- To use a Redis-backed message bus instead (recommended for
    # -- multi-process / production deployments), uncomment the lines
    # -- below and replace the InMemoryMessageBus() above:
    #
    # from agentscope.app.message_bus import RedisMessageBus
    # message_bus=RedisMessageBus(
    #     host="localhost",
    #     port=6379,
    # ),
    workspace_manager=AutoCleanupDockerWorkspaceManager(
        basedir=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "workspaces",
        ),
        # The default MCP servers that will be added into the workspace
        default_mcps=default_mcps,
        # Seed the A2UI generation skill into every new workspace so the
        # agent can read the full protocol spec on demand via the Skill
        # tool, keeping the system prompt compact.
        skill_paths=[
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "skills",
                "a2ui-generation",
            ),
        ],
    ),
    # Knowledge base feature — backed by an in-memory Qdrant store. The
    # CollectionPerKbManager allocates one collection per knowledge base,
    # so any embedding dimension is allowed.
    knowledge_base_manager=CollectionPerKbManager(
        storage=storage,
        vector_store=vector_store,
    ),
    # Chunker classes users can pick from when creating a knowledge base;
    # the chosen type and parameters are pinned on the knowledge base.
    knowledge_chunkers=[ApproxTokenChunker],
    # Resource hubs the UI browses under /hub. Neither needs credentials
    # of its own — an individual MCP card declares whatever key it wants
    # from the user in its ``inputs_schema``. Passing a ClawHub token
    # only raises the rate limit.
    mcp_hubs=[GitHubMCPHub()],
    skill_hubs=[ClawSkillHub(api_token=os.getenv("CLAWHUB_API_TOKEN"))],
    # Customize your own subagent templates
    custom_subagent_templates=[
        SubAgentTemplate(
            type="explorer",
            description=(
                "Read-only agents specialized in exploration tasks. It can "
                "read files but cannot modify, create, or delete them. Use "
                "this agent type when you need to investigate the codebase, "
                "understand its structure, or gather information from files "
                "to support planning—without making any changes."
            ),
            system_prompt_template="""You are {member_name}, an explorer \
agent in team '{team_name}' led by {leader_name}.

Team purpose: {team_description}

Your role: {member_description}

## Responsibilities
- Complete the exploration tasks assigned by the team leader.
- You are read-only: you may inspect files and the codebase, but you must \
never modify, create, or delete anything.

## Reporting
- Always report the task result back to {leader_name} using the TeamSay \
tool, whether the task succeeds or fails.
- Keep your private reasoning private; only share conclusions and findings \
that the leader needs.

Note: `TeamSay` is your ONLY channel to communicate with {leader_name} and \
the other team members. Any other output you produce is invisible to them, \
so anything you want them to see MUST be sent through `TeamSay`.""",
            permission_context=PermissionContext(
                # Read-only
                mode=PermissionMode.EXPLORE,
            ),
        ),
    ],
    # Long-term memory. The default PER_AGENT workspace isolation makes
    # the memory survive across sessions of the same agent.
    extra_agent_middlewares=longterm_memory_factory,
    # A2UI custom tool — lets agents emit declarative UI surfaces
    # rendered by the @a2ui/react frontend.
    extra_agent_tools=a2ui_tool_factory,
    # Use our custom Agent subclass that runs a 3-step CS pipeline for
    # the "Customer Service Agent" and recovers from stuck HITL sessions
    # for all other agents.
    custom_agent_cls=CSPipelineAgent,
    extra_middlewares=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
    channels=[
        DingTalkChannel,
        DiscordChannel,
        FeishuChannel,
    ],
)


# Register the custom pipeline router — per-step instruction pipeline
# that chains agents, giving each its own instruction combined with the
# previous agent's output.
from pipeline_router import pipeline_router

app.include_router(pipeline_router)

# Register the goal pipeline router — exposes the framework's
# GoalPipeline (executor + verifier loop) via HTTP endpoints.
from goal_pipeline_router import goal_pipeline_router

app.include_router(goal_pipeline_router)

# Register the custom model management router — lets users add/remove
# custom model names and run connection tests from the credential page.
from custom_model_router import custom_model_router

app.include_router(custom_model_router)

# Register the custom credential router — lets users create/list/delete
# custom credentials with a user-defined name, API base URL, and API key.
from custom_credential_router import custom_credential_router

app.include_router(custom_credential_router)


# ── Seed built-in agents on startup ─────────────────────────────
# Inner agents (Customer Service Agent + 4 pipeline sub-agents) are
# created automatically the first time the server starts.  The user
# ID is configurable via the ``INNER_AGENT_USER_ID`` env var so
# deployments can choose where the agents appear.
_INNER_AGENT_USER_ID = os.getenv("INNER_AGENT_USER_ID", "inner")


async def _seed_inner_agents() -> None:
    """Create built-in agents if they don't already exist."""
    await seed_inner_agents(storage, user_id=_INNER_AGENT_USER_ID)


# Wrap the framework lifespan so seeding runs **after** storage and
# other resources are entered (the original lifespan opens the Redis
# connection, message bus, etc.).  Seeding happens once on startup,
# before the first request is served.
from contextlib import asynccontextmanager

_orig_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _lifespan_with_seeding(app_obj):
    """Wrap the original lifespan to seed agents on startup."""
    async with _orig_lifespan(app_obj):
        await _seed_inner_agents()
        yield


app.router.lifespan_context = _lifespan_with_seeding


if __name__ == "__main__":
    # Start the service.
    # NOTE: reload=True forces uvicorn's use_subprocess=True, which on
    # Windows makes it pick SelectorEventLoop — that loop does NOT support
    # asyncio.create_subprocess_exec (raises NotImplementedError), breaking
    # workspace/skill listing and all shell-based tool operations.
    # Disabling reload lets uvicorn use ProactorEventLoop on Windows.
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
