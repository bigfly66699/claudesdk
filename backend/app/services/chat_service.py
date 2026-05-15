from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from claude_code_sdk import query
from claude_code_sdk.types import ClaudeCodeOptions, ResultMessage, StreamEvent

from app import state
from app.config import settings

from . import sandbox_service, session_service


def build_claude_options(model: str | None, sandbox_path: Path | None = None) -> ClaudeCodeOptions:
    settings_file = None
    if sandbox_path:
        settings_file = str(sandbox_path / ".claude" / "settings.json")

    return ClaudeCodeOptions(
        continue_conversation=True,
        include_partial_messages=True,
        model=model or settings.anthropic_model,
        permission_mode="default",
        cwd=str(sandbox_path) if sandbox_path else None,
        settings=settings_file,
        env={
            "ANTHROPIC_API_KEY": settings.anthropic_auth_token,
            "ANTHROPIC_BASE_URL": settings.anthropic_base_url,
            "CLAUDE_CODE_SIMPLE": "1",
        },
    )


async def stream_chat_sse(
    session_id: str,
    user_message: str,
    model: str | None,
    meta: dict,
) -> AsyncIterator[str]:
    sandbox_path = sandbox_service.sandbox_path_for(session_id)
    skills = session_service.normalize_skills(meta.get("skills"))
    if not sandbox_path.exists():
        sandbox_service.create_sandbox(session_id, skills=skills)
    options = build_claude_options(model, sandbox_path=sandbox_path)

    assistant_text = ""
    saved = False

    def persist_assistant(force: bool = False) -> None:
        nonlocal saved
        if saved:
            return
        if not force and not assistant_text.strip():
            return
        meta["messages"].append({"role": "assistant", "content": assistant_text})
        meta["updated_at"] = time.time()
        session_service.save_session(session_id)
        saved = True

    try:
        query_gen = query(prompt=user_message, options=options)
        async for msg in query_gen:
            if session_id in state.stopped_sessions:
                state.stopped_sessions.discard(session_id)
                persist_assistant(force=True)
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
                persist_assistant(force=True)
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return

        if assistant_text.strip():
            persist_assistant(force=True)
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    except asyncio.CancelledError:
        persist_assistant(force=True)
        raise
    except Exception as e:
        err = json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)
        yield f"data: {err}\n\n"
        persist_assistant(force=True)
    finally:
        state.active_chats.discard(session_id)
