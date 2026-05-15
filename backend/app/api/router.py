from fastapi import APIRouter

from app.api.routes import chat, sessions, skills

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(sessions.router)
api_router.include_router(skills.router)
