import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import state
from app.schemas.requests import ChatRequest
from app.services import chat_service, session_service

router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest):
    session_id = session_service.validate_session_id(req.session_id)

    if session_id in state.active_chats:
        raise HTTPException(status_code=409, detail="Session is busy")

    meta = session_service.ensure_session(session_id)
    meta["messages"].append({"role": "user", "content": req.message})
    meta["updated_at"] = time.time()
    session_service.save_session(session_id)

    state.stopped_sessions.discard(session_id)
    state.active_chats.add(session_id)

    async def event_stream():
        async for chunk in chat_service.stream_chat_sse(
            session_id, req.message, req.model, meta
        ):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")
