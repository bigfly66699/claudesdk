import time

from fastapi import APIRouter

from app import state
from app.schemas.requests import NewSessionRequest, UpdateSkillsRequest
from app.services import sandbox_service, session_service

router = APIRouter()


@router.post("/sessions/new")
async def new_session(req: NewSessionRequest):
    session_id = session_service.validate_session_id(req.session_id)
    skills = session_service.normalize_skills(req.skills)
    now = time.time()
    state.sessions[session_id] = {
        "messages": [],
        "skills": skills,
        "created_at": now,
        "updated_at": now,
    }
    session_service.save_session(session_id)
    sandbox_service.create_sandbox(session_id, skills=skills)
    return {"status": "ok", "session_id": session_id, "title": req.title, "skills": skills}


@router.get("/sessions")
async def list_sessions():
    result = []
    for sid, meta in state.sessions.items():
        result.append({
            "session_id": sid,
            "title": session_service.session_title(meta),
            "message_count": len(meta.get("messages", [])),
            "skills": meta.get("skills", []),
            "updated_at": meta.get("updated_at", 0),
        })
    result.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"sessions": result}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    session_service.validate_session_id(session_id)
    state.sessions.pop(session_id, None)
    session_service.delete_session_file(session_id)
    sandbox_service.delete_sandbox(session_id)
    state.stopped_sessions.discard(session_id)
    state.active_chats.discard(session_id)
    return {"status": "ok"}


@router.post("/sessions/{session_id}/stop")
async def stop_generation(session_id: str):
    session_service.validate_session_id(session_id)
    state.stopped_sessions.add(session_id)
    return {"status": "ok"}


@router.post("/sessions/{session_id}/skills")
@router.patch("/sessions/{session_id}/skills")
async def update_session_skills(session_id: str, req: UpdateSkillsRequest):
    session_service.validate_session_id(session_id)
    meta = session_service.ensure_session(session_id)
    skills = session_service.normalize_skills(req.skills)
    meta["skills"] = skills
    meta["updated_at"] = time.time()
    session_service.save_session(session_id)
    sandbox_service.update_sandbox_skills(session_id, skills)
    return {"status": "ok", "skills": skills}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    session_service.validate_session_id(session_id)
    meta = session_service.ensure_session(session_id)
    return {
        "session_id": session_id,
        "messages": meta.get("messages", []),
        "skills": meta.get("skills", []),
    }
