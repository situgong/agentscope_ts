---
skill: project-feature
status: done
date: 2026-08-28
title: Customer Service Pipelines — Sequential + Goal
---

# Change Doc: Customer Service Pipelines

## Goal

Create two pipelines for the customer service agent:
1. **Sequential Pipeline**: Check question → Solve → Check response
2. **Goal Pipeline**: Executor (Customer Service Agent) + Verifier loop

## Design

### Agents to Create

| Agent Name | Role | Pipeline |
|---|---|---|
| CS Question Analyzer | Sequential Step 1 — classify & analyze | Sequential |
| CS Problem Solver | Sequential Step 2 — solve the problem | Sequential |
| CS Response Reviewer | Sequential Step 3 — review the response | Sequential |
| CS Response Verifier | Goal Verifier — verify response quality | Goal |

The existing **Customer Service Agent** (`c6c55f5d...`) serves as the
executor in the Goal pipeline.

### Pipeline 1 — Sequential

| Step | Agent | Instruction |
|---|---|---|
| 1 | CS Question Analyzer | Analyze the customer's question: classify type, urgency, complexity. Output a structured analysis. |
| 2 | CS Problem Solver | Based on the analysis above, provide a solution to the customer's problem. |
| 3 | CS Response Reviewer | Review the proposed solution for accuracy, tone, completeness, and professionalism. Output the final approved response. |

### Pipeline 2 — Goal

| Role | Agent | Instruction |
|---|---|---|
| Executor | Customer Service Agent | Handle the customer's request and provide a response. |
| Verifier | CS Response Verifier | Verify whether the response is accurate, complete, and professional. |

Max iterations: 5

### Implementation

A Python setup script (`setup_cs_agents.py`) creates all 4 agents via
the `POST /agent/` API. After running the script, the agents appear in
the web UI's agent selector and can be used in the Pipeline page.

## Complexity Assessment

| Dimension | Value |
|-----------|-------|
| New/modified files | 1 (setup script) |
| DB/API changes | No (uses existing API) |
| Frontend changes | No (existing UI supports both modes) |
| Cross-module impact | No |

**Level: S (Simple)** — Phases 1-5 + 8 + 9.

## Backward Compatibility

Fully additive — no existing code is modified.
