from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.skills_data import ALL_SKILLS, SKILL_TO_PLUGIN

from . import session_service


def sandbox_path_for(session_id: str) -> Path:
    session_service.validate_session_id(session_id)
    path = (settings.sandbox_dir / session_id).resolve()
    if settings.sandbox_dir.resolve() not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return path


def _build_session_settings(skills: list[str] | None = None) -> str:
    settings_dict: dict = {
        "env": {},
        "permissions": {},
        "projects": {},
    }
    if skills is not None:
        enabled_plugins = {}
        for s in skills:
            if s in SKILL_TO_PLUGIN:
                enabled_plugins[SKILL_TO_PLUGIN[s]] = True
        settings_dict["enabledPlugins"] = enabled_plugins
        settings_dict["skillOverrides"] = {s: "on" if s in skills else "off" for s in ALL_SKILLS}
    return json.dumps(settings_dict, ensure_ascii=False)


def create_sandbox(session_id: str, skills: list[str] | None = None) -> Path:
    sandbox_path = sandbox_path_for(session_id)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    claude_dir = sandbox_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "settings.json").write_text(
        _build_session_settings(skills), encoding="utf-8"
    )
    return sandbox_path


def update_sandbox_skills(session_id: str, skills: list[str] | None) -> None:
    sandbox_path = sandbox_path_for(session_id)
    if sandbox_path.exists():
        claude_dir = sandbox_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        (claude_dir / "settings.json").write_text(
            _build_session_settings(skills), encoding="utf-8"
        )
    else:
        create_sandbox(session_id, skills=skills)


def delete_sandbox(session_id: str) -> None:
    sandbox_path = sandbox_path_for(session_id)
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path, ignore_errors=True)
