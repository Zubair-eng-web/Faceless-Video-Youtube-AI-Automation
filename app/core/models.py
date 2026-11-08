"""Data models: Gemini se aane wala data aur final storyboard."""
from pydantic import BaseModel


class TopicIdea(BaseModel):
    title: str
    angle: str
    why_trending: str


class TopicList(BaseModel):
    topics: list[TopicIdea]


class SceneDraft(BaseModel):
    narration: str
    visual_description: str
    search_query: str


class ScriptDraft(BaseModel):
    title: str
    hook: str
    scenes: list[SceneDraft]


class Scene(BaseModel):
    number: int
    narration: str
    visual_description: str
    search_query: str
    duration: float


class Storyboard(BaseModel):
    title: str
    hook: str
    language: str = "English"
    scenes: list[Scene]

    @property
    def total_duration(self) -> float:
        return round(sum(s.duration for s in self.scenes), 1)

    @property
    def full_narration(self) -> str:
        return " ".join(s.narration for s in self.scenes)
