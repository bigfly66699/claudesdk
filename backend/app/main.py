from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.services.session_service import load_all_sessions
from app.services.skills_catalog import reload_skills_catalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    reload_skills_catalog()
    load_all_sessions()
    yield


app = FastAPI(title="AI Chat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
