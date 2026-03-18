from __future__ import annotations
from pydantic import BaseModel, Field


class SegmentDefinition(BaseModel):
    name: str
    description: str
    count: int | None = None


class ScenarioBrief(BaseModel):
    world_description: str
    rules_or_context: list[str] = Field(default_factory=list)
    proposed_change: str | None = None
    target_segments: list[SegmentDefinition] | None = None
    population: int = 25
    duration_days: int = 90
