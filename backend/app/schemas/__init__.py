"""Request/response schemas for the REST API (the frontend contract)."""
from typing import Literal

from pydantic import BaseModel, Field

MemoryTypeLit = Literal["semantic", "episodic", "procedural", "working"]
ConfirmationLit = Literal["confirmed", "tentative"]
TaskStatusLit = Literal["open", "in_progress", "blocked", "done"]
PriorityLit = Literal["high", "medium", "low"]


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    memory_type: MemoryTypeLit = "semantic"
    confirmation: ConfirmationLit = "confirmed"
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="user", max_length=200)
    supersedes_id: int | None = None


class MemoryPatch(BaseModel):
    content: str | None = Field(default=None, max_length=5000)
    memory_type: MemoryTypeLit | None = None
    confirmation: ConfirmationLit | None = None
    status: Literal["active", "superseded"] | None = None
    tags: list[str] | None = Field(default=None, max_length=20)


class DecisionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    status: Literal["confirmed", "proposed"] = "confirmed"
    supersedes_decision_id: int | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    priority: PriorityLit = "medium"
    status: TaskStatusLit = "open"


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    priority: PriorityLit | None = None
    status: TaskStatusLit | None = None


class MissionIn(BaseModel):
    request: str = Field(min_length=1, max_length=2000)
