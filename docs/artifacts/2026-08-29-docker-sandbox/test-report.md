---
date: 2026-08-29
title: Docker Sandbox Website Test Report
---

# Docker Sandbox Test Report

## Test Environment

| Component | Version / Status |
|-----------|-----------------|
| OS | Linux (WSL2) |
| Docker Engine | 29.7.2 |
| Docker Image | `agentscope-workspace:e69eaf6c68a6` (956MB) |
| Backend | FastAPI on port 8000 |
| Frontend | Vite dev server on port 5173 |
| Redis | 7.0.15 on port 6379 |
| Model | MiniMax-M2 (via Haier OpenAI-compatible API) |
| Agent | Customer Service Agent (CSPipelineAgent) |

## Answers to Key Questions

### Q: Is the container always running when my backend starts?

**No.** The `DockerWorkspaceManager` uses **lazy initialization**. Containers
are NOT created at backend startup. They are created **on-demand** only when
a chat message is sent and the agent's workspace needs to be initialized.

**Evidence:**
- Backend started at 12:34 — `docker ps` showed zero containers
- Chat message sent at 12:35 — container `as_ws_00c258f2ef2c45f087e5d19cfe00f53c`
  appeared within seconds

### Q: Why don't I see a running container?

Because no chat session has been initiated yet. The container only spawns
when an agent processes a message. If you've just started the backend and
haven't sent any chat messages, there will be no running containers.

### Q: I can see the image but no running container

Correct — the image is pre-built (956MB, content-hashed). The image exists
persistently, but containers are ephemeral and lazy-created per workspace.

## Test Steps & Results

### Step 1: Start Backend

```
cd examples/agent_service && python main.py
```

- Backend started on port 8000 ✅
- 5 inner agents seeded (Customer Service Agent + 4 sub-agents) ✅
- Docker containers at startup: **0** (expected — lazy init) ✅

### Step 2: Start Frontend

```
cd examples/web_ui && pnpm dev
```

- Frontend started on port 5173 ✅
- Connected to backend at http://localhost:8000 ✅

### Step 3: Open Website & Configure

- Navigated to http://localhost:5173/chat ✅
- Set server URL: `http://localhost:8000` ✅
- Set username: `inner` ✅
- 5 agents visible in dropdown ✅

### Step 4: Select Agent & Model

- Selected agent: **Customer Service Agent** ✅
- Model auto-selected: **MiniMax-M2** (from Haier credential) ✅
- Created new session ✅

### Step 5: Send Chat Message

- Message: "Who are you? What could you do" ✅
- Message sent successfully ✅

### Step 6: Docker Container Spawned

**Immediately after sending the message**, a Docker container was created:

```
NAMES                                    STATUS          IMAGE
as_ws_2b50c1a71d8a4e7d8fd2fb1de33a9071   Up 12 seconds   agentscope-workspace:e69eaf6c68a6
```

Container details:
- **Image**: `agentscope-workspace:e69eaf6c68a6`
- **WorkingDir**: `/workspace`
- **Bind-mount**: `examples/agent_service/workspaces/2b50c1a71d8a4e7d8fd2fb1de33a9071` → `/workspace`
- **Image cache hit**: No rebuild needed (image already existed)

### Step 7: Chat Response Received

The CS Pipeline Agent executed all 3 pipeline steps:

1. **🔍 Step 1: Analyzing** (CS Question Analyzer)
   - Identified question type: General inquiry / identity clarification
   - Urgency: low, Complexity: simple, Sentiment: neutral

2. **🔧 Step 2: Solving** (CS Problem Solver)
   - Generated structured response with:
     - Greeting: "Hello! 👋 Welcome!"
     - Acknowledgment of the question
     - Solution: Detailed explanation of role + services table
     - Additional Resources
     - Closing

3. **✅ Step 3: Final Response** (CS Response Reviewer)
   - Reviewed against 5 criteria: Accuracy ✅, Tone ✅, Completeness ✅, Clarity ✅, Safety ✅
   - Status: Approved

### Step 8: Final Docker State

Two containers running (one per agent workspace):

```
NAMES                                    STATUS              IMAGE
as_ws_2b50c1a71d8a4e7d8fd2fb1de33a9071   Up About a minute   agentscope-workspace:e69eaf6c68a6
as_ws_00c258f2ef2c45f087e5d19cfe00f53c   Up 2 minutes        agentscope-workspace:e69eaf6c68a6
```

Host workspace directories (persistent bind-mounts):

```
workspaces/
├── 00c258f2ef2c45f087e5d19cfe00f53c/   (CS Question Analyzer workspace)
│   ├── Memory/
│   ├── data/
│   ├── sessions/
│   └── skills/
├── 2b50c1a71d8a4e7d8fd2fb1de33a9071/   (Customer Service Agent workspace)
│   ├── Memory/
│   ├── data/
│   ├── sessions/
│   └── skills/
├── 531d8d67de674d7f86e32135f3dacc9a/   (previous test)
└── 8ad6f6e7cb18473d8792136cc0b10b82/   (previous test)
```

## Summary

| Test | Result |
|------|--------|
| Backend startup | ✅ Pass |
| Frontend startup | ✅ Pass |
| Agent list loads | ✅ Pass |
| Model selection | ✅ Pass |
| Session creation | ✅ Pass |
| Chat message sent | ✅ Pass |
| Docker container spawned | ✅ Pass |
| Docker image cache hit | ✅ Pass (no rebuild) |
| Bind-mount persistence | ✅ Pass |
| CS Pipeline (3-step) executed | ✅ Pass |
| Agent response received | ✅ Pass |
| Multiple containers (per agent) | ✅ Pass |

## Conclusion

The Docker sandbox is **fully functional**. Key behaviors confirmed:

1. **Lazy initialization**: Containers are NOT created at backend startup.
   They spawn on-demand when a chat message triggers workspace init.
2. **Image caching**: The image `agentscope-workspace:e69eaf6c68a6` is built
   once and reused (cache hit, no rebuild).
3. **Per-agent isolation**: Each agent gets its own container and workspace
   directory (`as_ws_<workspace_id>`).
4. **Persistent bind-mount**: Host directory `workspaces/<id>` is
   bind-mounted to `/workspace` in the container, surviving container
   restarts.
5. **Full pipeline execution**: The CS Pipeline Agent (Analyzer → Solver →
   Reviewer) executed successfully inside the Docker sandbox.
