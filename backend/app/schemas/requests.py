from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str
    model: str | None = None


class NewSessionRequest(BaseModel):
    session_id: str
    title: str = "新对话"
    skills: list[str] | None = None


class UpdateSkillsRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
