from fastapi import APIRouter

from app.api.routes import chat, sessions

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(sessions.router)
