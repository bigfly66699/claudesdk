# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Chat application with session management, conversation persistence, and SSE streaming. Built with Vue 3 frontend and FastAPI backend.

- **Frontend**: Vue 3 SPA, Vite dev server (port 3000), Element Plus UI components
- **Backend**: FastAPI (port 8000), `claude-code-sdk` for LLM calls, session persistence via JSON files, per-session sandbox isolation

## Directory Structure

```
backend/
  main.py                    # ASGI entry — re-exports app from app.main
  requirements.txt           # Python deps
  .env                       # API credentials (never commit)
  app/
    main.py                  # FastAPI app factory, lifespan, CORS, router mount
    config.py                # Settings dataclass, loads .env
    state.py                 # In-memory mutable state (sessions, stopped, active_chats)
    skills_data.py           # ALL_SKILLS list, SKILL_TO_PLUGIN mapping
    api/
      router.py              # Mounts chat and sessions routers
      routes/
        chat.py              # POST /api/chat — SSE streaming endpoint
        sessions.py          # Session CRUD + skill management endpoints
    schemas/
      requests.py            # Pydantic request models
    services/
      chat_service.py        # Claude Code SDK integration, SSE event generation
      session_service.py     # Session persistence, validation, title extraction
      sandbox_service.py     # Per-session sandbox creation, skill settings, cleanup
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

### Backend Module Layout

The backend was refactored from a single `main.py` into a modular package (`backend/app/`). The top-level `backend/main.py` re-exports `app` from `app.main` for `uvicorn` compatibility.

Key modules:
- **`config.py`** — Loads `.env` at import time, provides frozen `Settings` dataclass with paths for `data_dir` and `sandbox_dir`
- **`state.py`** — Process-wide mutable dicts/sets: `sessions`, `stopped_sessions`, `active_chats`
- **`skills_data.py`** — Skill identifiers and plugin source mappings

### Chat Flow (`chat_service.py`)

1. Frontend POSTs to `/api/chat` with `message`, `session_id`, optional `model`
2. Session is validated and ensured via `session_service`
3. Sandbox path is resolved; sandbox created if missing with skill settings
4. `claude-code-sdk` `query()` is called with `ClaudeCodeOptions` (cwd=settings file/env vars)
5. SSE stream yields `data:` lines for `text`, `done`, `stopped`, `error` events
6. Assistant text is accumulated and persisted to session JSON on completion/stop/error
7. `active_chats` set prevents concurrent requests to the same session (409 conflict)

### Session Persistence (`session_service.py`)

- JSON files in `backend/data/{session_id}.json`
- Session metadata includes: `messages`, `skills`, `created_at`, `updated_at`
- Legacy sessions (array-only format) are auto-migrated on load with default metadata
- `validate_session_id()` enforces `sess_<timestamp>_<6chars>` pattern to prevent path traversal
- Path resolution check ensures files stay within `data_dir`

### Sandbox Isolation (`sandbox_service.py`)

Each session gets an isolated working directory under `backend/sandbox/{session_id}/`:

- `cwd` in `ClaudeCodeOptions` sets Claude Code's working directory
- Per-session `.claude/settings.json` controls `enabledPlugins` and `skillOverrides`
- `CLAUDE_CODE_SIMPLE=1` env var reduces Claude Code output verbosity
- `update_sandbox_skills()` can update settings for existing sandboxes

### Skill System

Skills are controlled via per-session `skillOverrides` in `.claude/settings.json`:

- `ALL_SKILLS`: `frontend-design`, `skill-creator`, `pw-browse`, `pw-launch`, `pw-close`, `pw-test`
- `SKILL_TO_PLUGIN`: Maps each skill to its plugin source (e.g., `pw-browse` → `pw-skill@pw-skill`)
- Selected skills set `enabledPlugins` to load only corresponding plugins, and `skillOverrides` to show/hide slash commands
- Unselected skills are set to `"off"` in skillOverrides, selected to `"on"`
- `normalize_skills()` filters to only valid skills from `ALL_SKILLS`

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message, returns SSE stream (409 if session busy) |
| POST | `/api/sessions/new` | Create session with optional skills |
| GET | `/api/sessions` | List all sessions (sorted by updated_at desc) |
| DELETE | `/api/sessions/{id}` | Delete session + sandbox + state cleanup |
| POST | `/api/sessions/{id}/stop` | Signal stop for running generation |
| GET | `/api/sessions/{id}/history` | Get session messages + skills |
| POST/PATCH | `/api/sessions/{id}/skills` | Update session skills (live updates sandbox) |

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
