# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Chat application with session management, conversation persistence, and SSE streaming. Built with Vue 3 frontend and FastAPI backend.

- **Frontend**: Vue 3 SPA, Vite dev server (port 3000), Ant Design Vue UI components
- **Backend**: FastAPI (port 8000), `claude-code-sdk` for LLM calls, session persistence via JSON files

## Directory Structure

```
backend/
  main.py          # FastAPI app: chat, session CRUD, SSE streaming
  requirements.txt # Python deps
  .env             # API credentials (never commit)
  data/            # JSON session files (auto-created, auto-loaded on startup)
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
Kill conflicting process: `netstat -ano | grep :8000` then `taskkill //PID <pid> //F`

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
- Text deltas extracted from `StreamEvent.event.delta.text` when `evt.type == "content_block_delta"` and `delta.type == "text_delta"`.
- **SSE streaming**: Response events prefixed with `data: ` and `\n\n` separator.
- **Session persistence**: JSON files in `backend/data/`. Loaded into memory on startup via `lifespan`. Each save writes the full session file.
- **Stop mechanism**: `stopped_sessions` set checked during stream iteration. Frontend calls `POST /api/sessions/{id}/stop`.
- **Multi-turn**: `continue_conversation=True` in `ClaudeCodeOptions` maintains conversation context across `query()` calls.
- **Config**: Loaded from `.env` — `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`.

### Frontend (`frontend/src/App.vue`)

- Single Vue component containing all UI and logic.
- SSE client parses `data:` prefixed lines, handles `text`, `done`, `stopped`, `error` event types.
- Session list sidebar: load, switch, create, delete sessions.
- Input clearing uses `inputKey` ref to force textarea component re-render (fixes Ant Design Vue sync issues).
- Input area `max-width: min(85%, 1780px)` for responsive width.

### Vite Proxy (`frontend/vite.config.js`)

- `/api` routes proxied to `http://127.0.0.1:8000`
- `changeOrigin: false` is required for SSE to work through the proxy
- Custom `proxyReq` handler sets `Content-Length` for POST bodies
- Custom `proxyRes` handler sets `connection: keep-alive` for SSE streams

## Known Issues

- SDK logs `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` on each request — this is a known anyio task group cleanup bug in `claude-code-sdk` and does not affect functionality.
