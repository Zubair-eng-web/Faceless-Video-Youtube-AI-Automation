"""API ke request models."""
from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    niche: str = ""
    language: str = "English"
    voice: str | None = None


class GenerateRequest(BaseModel):
    topic: str | None = None
    channel_id: int | None = None
    niche: str | None = None
    language: str | None = None
    seconds: int = Field(40, ge=15, le=90)
    voice: str | None = None
