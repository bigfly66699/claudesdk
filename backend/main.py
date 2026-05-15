from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from claude_code_sdk import query
from claude_code_sdk.types import (
    ClaudeCodeOptions,
    ResultMessage,
    StreamEvent,
)

load_dotenv()

ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SANDBOX_DIR = Path(__file__).parent / "sandbox"
SANDBOX_DIR.mkdir(exist_ok=True)

sessions: dict[str, list[dict]] = {}
stopped_sessions: set[str] = set()


def save_session(session_id: str):
    path = DATA_DIR / f"{session_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions.get(session_id, []), f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> list[dict]:
    path = DATA_DIR / f"{session_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_all_sessions():
    for p in DATA_DIR.glob("*.json"):
        sid = p.stem
        sessions[sid] = load_session(sid)


def delete_session_file(session_id: str):
    path = DATA_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


ALL_SKILLS = [
    "frontend-design",
    "skill-creator",
    "pw-browse",
    "pw-launch",
    "pw-close",
    "pw-test",
]

SKILL_TO_PLUGIN = {
    "frontend-design": "frontend-design@claude-plugins-official",
    "skill-creator": "skill-creator@claude-plugins-official",
    "pw-browse": "pw-skill@pw-skill",
    "pw-launch": "pw-skill@pw-skill",
    "pw-close": "pw-skill@pw-skill",
    "pw-test": "pw-skill@pw-skill",
}


def _build_session_settings(skills: list[str] | None = None) -> str:
    settings: dict = {
        "env": {},
        "permissions": {},
        "projects": {},
    }
    if skills is not None:
        enabled_plugins = {}
        for s in skills:
            if s in SKILL_TO_PLUGIN:
                enabled_plugins[SKILL_TO_PLUGIN[s]] = True
        settings["enabledPlugins"] = enabled_plugins
        settings["skillOverrides"] = {s: "on" if s in skills else "off" for s in ALL_SKILLS}
    return json.dumps(settings, ensure_ascii=False)


def create_sandbox(session_id: str, skills: list[str] | None = None) -> Path:
    sandbox_path = SANDBOX_DIR / session_id
    sandbox_path.mkdir(parents=True, exist_ok=True)
    claude_dir = sandbox_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "settings.json").write_text(
        _build_session_settings(skills), encoding="utf-8"
    )
    return sandbox_path


def delete_sandbox(session_id: str):
    sandbox_path = SANDBOX_DIR / session_id
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path, ignore_errors=True)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    model: str | None = None


class NewSessionRequest(BaseModel):
    session_id: str
    title: str = "新对话"
    skills: list[str] | None = None


def _build_options(model: str | None, sandbox_path: Path | None = None) -> ClaudeCodeOptions:
    settings_file = None
    if sandbox_path:
        settings_file = str(sandbox_path / ".claude" / "settings.json")

    return ClaudeCodeOptions(
        continue_conversation=True,
        include_partial_messages=True,
        model=model or ANTHROPIC_MODEL,
        permission_mode="default",
        cwd=str(sandbox_path) if sandbox_path else None,
        settings=settings_file,
        env={
            "ANTHROPIC_API_KEY": ANTHROPIC_AUTH_TOKEN,
            "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
            "CLAUDE_CODE_SIMPLE": "1",
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_all_sessions()
    yield


app = FastAPI(title="AI Chat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.session_id not in sessions:
        sessions[req.session_id] = []

    sessions[req.session_id].append({"role": "user", "content": req.message})
    save_session(req.session_id)

    stopped_sessions.discard(req.session_id)
    sandbox_path = SANDBOX_DIR / req.session_id
    if not sandbox_path.exists():
        create_sandbox(req.session_id)
    options = _build_options(req.model, sandbox_path=sandbox_path)

    async def event_stream():
        assistant_text = ""
        query_gen = None
        try:
            query_gen = query(prompt=req.message, options=options)
            async for msg in query_gen:
                if req.session_id in stopped_sessions:
                    stopped_sessions.discard(req.session_id)
                    sessions[req.session_id].append({"role": "assistant", "content": assistant_text})
                    save_session(req.session_id)
                    yield f"data: {json.dumps({'type': 'stopped'}, ensure_ascii=False)}\n\n"
                    return

                if isinstance(msg, StreamEvent):
                    evt = msg.event
                    if evt.get("type") == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            assistant_text += text
                            data = json.dumps({"type": "text", "content": text}, ensure_ascii=False)
                            yield f"data: {data}\n\n"
                elif isinstance(msg, ResultMessage):
                    sessions[req.session_id].append({"role": "assistant", "content": assistant_text})
                    save_session(req.session_id)
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                    return

        except asyncio.CancelledError:
            pass
        except Exception as e:
            err = json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

        sessions[req.session_id].append({"role": "assistant", "content": assistant_text})
        save_session(req.session_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/sessions/new")
async def new_session(req: NewSessionRequest):
    sessions[req.session_id] = []
    save_session(req.session_id)
    create_sandbox(req.session_id, skills=req.skills)
    return {"status": "ok", "session_id": req.session_id, "title": req.title}


@app.get("/api/sessions")
async def list_sessions():
    result = []
    for sid in sessions:
        msgs = sessions[sid]
        title = "新对话"
        for m in msgs:
            if m["role"] == "user":
                title = m["content"][:50]
                break
        result.append({"session_id": sid, "title": title, "message_count": len(msgs)})
    return {"sessions": result}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    sessions.pop(session_id, None)
    delete_session_file(session_id)
    delete_sandbox(session_id)
    return {"status": "ok"}


@app.post("/api/sessions/{session_id}/stop")
async def stop_generation(session_id: str):
    stopped_sessions.add(session_id)
    return {"status": "ok"}


@app.get("/api/sessions/{session_id}/history")
async def get_history(session_id: str):
    return {"session_id": session_id, "messages": sessions.get(session_id, [])}
