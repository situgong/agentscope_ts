---
skill: project-feature
status: in-progress
date: 2026-08-29
---

# Test Plan: Auto-seed inner agents on backend startup

## Test Matrix

| # | Category | Scenario | Expected Result | Status |
|---|----------|----------|-----------------|--------|
| 1 | Positive | Fresh Redis, start backend → agents auto-created | 5 agents appear under user "inner" | ✅ Passed (Phase 5) |
| 2 | Positive | Restart backend with existing agents → no duplicates | Agent count stays at 5 | ✅ Passed (Phase 5) |
| 3 | Positive | `INNER_AGENT_USER_ID` env var set to custom value | Agents created under custom user ID | ⏳ Pending |
| 4 | Positive | `setup_cs_agents.py` still works against running server | Creates 4 sub-agents via HTTP API | ⏳ Pending |
| 5 | Boundary | Redis has partial agents (only 2 of 5) → restart | Missing 3 agents created, existing 2 untouched | ⏳ Pending |
| 6 | Boundary | Agent name collision with user-created agent | Inner agent created under "inner" user, no collision with other users | ✅ Passed (Phase 5) |
| 7 | Exception | Redis unavailable at startup | Startup hook logs error, server still starts | ⏳ Pending |
| 8 | Regression | Existing "kids" user agents still visible | No impact on other users' agents | ✅ Passed (Phase 5) |
| 9 | E2E | Start backend → open UI → select "Customer Service Agent" → chat | Agent appears in UI, 3-step pipeline works | ⏳ Pending |

## E2E Applicability

- **Frontend + Backend**: Yes — the UI should show auto-seeded agents
- **E2E test**: Start backend, verify agents via `GET /agent/` API, optionally verify in UI

## Notes

- Tests 1-2, 6, 8 passed in Phase 5 via direct Redis integration test
- Test 3 is implicitly covered by the env var default logic
- Test 9 (full E2E) will be executed in Phase 7
