from __future__ import annotations

import json
import re
import time
from pathlib import Path

from fastapi import HTTPException

from app import state
from app.config import settings
from app.services import skills_catalog

SESSION_ID_RE = re.compile(r"^sess_\d+_[a-z0-9]{6}$")


def validate_session_id(session_id: str) -> str:
    if not SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return session_id


def session_file_path(session_id: str) -> Path:
    validate_session_id(session_id)
    path = (settings.data_dir / f"{session_id}.json").resolve()
    if settings.data_dir.resolve() not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return path


def normalize_skills(skills: list[str] | None) -> list[str]:
    if not skills:
        return []
    valid = skills_catalog.SKILL_TO_PLUGIN.keys()
    filtered = [s for s in skills if s in valid]
    if not filtered:
        return []
    out = list(dict.fromkeys(filtered))
    for bundle in skills_catalog.BUNDLES:
        mids = bundle.get("member_ids") or []
        if any(m in out for m in mids):
            for m in mids:
                if m not in out:
                    out.append(m)
    return out


def empty_session_meta() -> dict:
    now = time.time()
    return {
        "messages": [],
        "skills": [],
        "created_at": now,
        "updated_at": now,
    }


def normalize_session_data(raw: object) -> dict:
    if isinstance(raw, list):
        now = time.time()
        return {
            "messages": raw,
            "skills": [],
            "created_at": now,
            "updated_at": now,
        }
    if isinstance(raw, dict):
        now = time.time()
        return {
            "messages": raw.get("messages", []),
            "skills": normalize_skills(raw.get("skills")),
            "created_at": raw.get("created_at", now),
            "updated_at": raw.get("updated_at", now),
        }
    return empty_session_meta()


def save_session(session_id: str) -> None:
    path = session_file_path(session_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.sessions[session_id], f, ensure_ascii=False, indent=2)


def load_session_file(session_id: str) -> dict:
    path = session_file_path(session_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return normalize_session_data(json.load(f))
    return empty_session_meta()


def load_all_sessions() -> None:
    for p in settings.data_dir.glob("*.json"):
        sid = p.stem
        if not SESSION_ID_RE.match(sid):
            continue
        state.sessions[sid] = load_session_file(sid)


def delete_session_file(session_id: str) -> None:
    path = session_file_path(session_id)
    if path.exists():
        path.unlink()


def ensure_session(session_id: str) -> dict:
    if session_id not in state.sessions:
        state.sessions[session_id] = load_session_file(session_id)
    return state.sessions[session_id]


def session_title(meta: dict) -> str:
    for m in meta.get("messages", []):
        if m.get("role") == "user":
            return m["content"][:50]
    return "新对话"
