# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Chat application with session management, conversation persistence, and SSE streaming. Built with Vue 3 frontend and FastAPI backend.

- **Frontend**: Vue 3 SPA, Vite dev server (port 3000), Element Plus UI components
- **Backend**: FastAPI (port 8000), `claude-code-sdk` for LLM calls, session persistence via JSON files, per-session sandbox isolation

## Directory Structure

```
backend/
  main.py          # FastAPI app: chat, session CRUD, SSE streaming, sandbox management
  requirements.txt # Python deps
  .env             # API credentials (never commit)
  data/            # JSON session files (auto-created, auto-loaded on startup)
  sandbox/         # Per-session working directories with isolated .claude/settings.json
frontend/
  src/App.vue      # Single-file Vue app (all UI + logic)
  src/main.js      # App entry, registers ElementPlus
  vite.config.js   # Vite config with /api proxy to port 8000
  package.json
  index.html
```

## Development Commands

**Backend:**
```
cd backend && uvicorn main:app --port 8000 --host 0.0.0.0
```
Kill conflicting process on Windows: `netstat -ano | grep :8000` then `taskkill //PID <pid> //F`

**Frontend:**
```
cd frontend && npm run dev
```
Build: `npm run build`

Vite proxy is configured to forward `/api` to `http://127.0.0.1:8000`.

## Architecture

### Backend (`backend/main.py`)

- Uses `claude-code-sdk` (not `anthropic` Python SDK). Requires Claude CLI to be installed globally via npm.
- `query()` function returns an async generator yielding `StreamEvent`, `ResultMessage`.
- Text deltas extracted from `StreamEvent.event` when `evt.type == "content_block_delta"` and `delta.type == "text_delta"`.
- **SSE streaming**: Response events prefixed with `data: ` and `\n\n` separator.
- **Session persistence**: JSON files in `backend/data/`. Loaded into memory on startup via `lifespan`. Each save writes the full session file.
- **Stop mechanism**: `stopped_sessions` set checked during stream iteration. Frontend calls `POST /api/sessions/{id}/stop`.
- **Multi-turn**: `continue_conversation=True` in `ClaudeCodeOptions` maintains conversation context across `query()` calls.
- **Config**: Loaded from `.env` — `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`. Default model: `qwen3.6-plus`.

### Sandbox Isolation

Each session gets an isolated working directory under `backend/sandbox/{session_id}/`:

- `cwd` option in `ClaudeCodeOptions` sets the working directory for Claude Code
- Per-session `.claude/settings.json` controls plugins and skill visibility
- `CLAUDE_CODE_SIMPLE=1` env var reduces Claude Code output verbosity
- Sandbox created on first chat or session creation, deleted on session delete

### Skill System

Custom skills are controlled via per-session `skillOverrides` in `.claude/settings.json`:

- `ALL_SKILLS`: `frontend-design`, `skill-creator`, `pw-browse`, `pw-launch`, `pw-close`, `pw-test`
- `SKILL_TO_PLUGIN`: Maps each skill to its plugin source (e.g., `pw-browse` → `pw-skill@pw-skill`)
- Selected skills set `enabledPlugins` to load only the corresponding plugins, and `skillOverrides` to show/hide slash commands
- Skills are NOT loaded in `--bare` mode — this flag was removed to allow plugin loading

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message, returns SSE stream |
| POST | `/api/sessions/new` | Create session with optional skills |
| GET | `/api/sessions` | List all sessions |
| DELETE | `/api/sessions/{id}` | Delete session + sandbox |
| POST | `/api/sessions/{id}/stop` | Signal stop for running generation |
| GET | `/api/sessions/{id}/history` | Get session message history |

### Frontend (`frontend/src/App.vue`)

- Single Vue component containing all UI and logic.
- SSE client parses `data:` prefixed lines, handles `text`, `done`, `stopped`, `error` event types.
- Session list sidebar: load, switch, create, delete sessions.
- Skill selector in header (multi-select) for per-session skill toggling.
- Input clearing uses `inputKey` ref to force textarea component re-render (fixes Element Plus sync issues).
- Input area `max-width: min(85%, 1780px)` for responsive width.
- Model selector dropdown in header.

### Vite Proxy (`frontend/vite.config.js`)

- `/api` routes proxied to `http://127.0.0.1:8000`
- `changeOrigin: false` is required for SSE to work through the proxy
- Custom `proxyReq` handler sets `Content-Length` for POST bodies
- Custom `proxyRes` handler sets `connection: keep-alive` for SSE streams

## Known Issues

- SDK logs `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` on each request — this is a known anyio task group cleanup bug in `claude-code-sdk` and does not affect functionality.
