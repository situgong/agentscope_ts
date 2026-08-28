# My AgentScope — Local Development Guide

Personal notes for running and extending the AgentScope examples on this machine.

## Environment

| Component | Value |
|-----------|-------|
| Repo path | `D:\haier\0-joy\26\github\agentscope_ts` |
| Branch | `my-examples` |
| Fork | `git@github.com:situgong/agentscope_ts.git` |
| Upstream | `https://github.com/agentscope-ai/agentscope.git` |
| Python | `.venv\Scripts\python.exe` (3.12.9) |
| SSH key passphrase | `ls` |

## Redis (Memurai — Windows Native)

This machine uses [Memurai](https://www.memurai.com/get-memurai) instead of Docker Redis.

| Item | Value |
|------|-------|
| Install path | `D:\Program Files\Memurai\` |
| CLI | `"D:\Program Files\Memurai\memurai-cli.exe"` |
| Port | 6379 (default, auto-starts as Windows service) |

### Common commands

```powershell
# Test connection
& "D:\Program Files\Memurai\memurai-cli.exe" ping

# Check key count
& "D:\Program Files\Memurai\memurai-cli.exe" dbsize

# List all keys
& "D:\Program Files\Memurai\memurai-cli.exe" keys "*"

# Flush all data (use when data is corrupted/incomplete)
& "D:\Program Files\Memurai\memurai-cli.exe" flushdb
```

## Start Frontend & Backend

```powershell
# Terminal 1 — Backend (FastAPI on port 8000)
cd D:\haier\0-joy\26\github\agentscope_ts\examples\agent_service
D:\haier\0-joy\26\github\agentscope_ts\.venv\Scripts\python.exe main.py

# Terminal 2 — Frontend (Vite on port 5174 + BFF on 5175)
cd D:\haier\0-joy\26\github\agentscope_ts\examples\web_ui
pnpm dev
```

Open `http://localhost:5174` and set API endpoint to `http://localhost:8000`.

## Stop Frontend & Backend

```powershell
Get-Process -Name "python","uvicorn","node" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*vite*" -or $_.CommandLine -like "*pnpm*" } |
  Stop-Process -Force
```

## Custom Features (in `examples/`)

| Feature | Backend | Frontend |
|---------|---------|----------|
| Custom Credentials | `custom_credential_router.py`, `custom_credentials.json` | `CreateCustomCredentialDialog.tsx`, `customCredential.ts` |
| Custom Models | `custom_model_router.py`, `custom_models.json`, `models/*.yaml` | `customModel.ts` |
| Pipeline | `pipeline_router.py` | `pages/pipeline/index.tsx`, `pipeline.ts` |
| A2UI Tool | `a2ui_tool.py`, `skills/a2ui-generation/SKILL.md` | `A2UISurface.tsx`, `A2UIRenderer.tsx` |
| Theme Switch | — | i18n `theme*` keys |
| Windows EventLoop | `main.py` (ProactorEventLoop) | — |
| DingTalk Channel | upstream `src/agentscope/app/channel/_dingtalk/` | — |

## Git Workflow

```powershell
# Always work on my-examples
git checkout my-examples

# Sync with upstream
git fetch upstream
git merge upstream/main

# Push to fork
git push origin my-examples
```

### Backup branch

```powershell
# Create backup before risky operations
git branch backup-<name> <commit-hash>
```

## Troubleshooting

### Feishu/DingTalk channel can't be added

Redis data may be incomplete. Flush and restart:

```powershell
& "D:\Program Files\Memurai\memurai-cli.exe" flushdb
# Then restart backend
```

### CORS error on `/workspace/skill`

Backend returns 500 (crash) → no CORS headers. Check backend logs for the stack trace.

### Page blank / wrong port

Vite dev server may land on 5174 (not 5173) if port is in use. Check terminal output for the actual port.

### Agent has no model

Create the agent with a `model_id` selected from the model dropdown.
