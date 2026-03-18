from __future__ import annotations
from pydantic import BaseModel, Field


class Personality(BaseModel):
    honesty: float = Field(default=0.5, ge=0.0, le=1.0)
    ambition: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    confrontational: float = Field(default=0.5, ge=0.0, le=1.0)
    conformity: float = Field(default=0.5, ge=0.0, le=1.0)
    brand_loyalty: float = Field(default=0.5, ge=0.0, le=1.0)
    price_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    social_proof: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty_seeking: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentPersona(BaseModel):
    id: int
    name: str
    role: str
    age: int
    personality: Personality
    background: str
    goals: list[str] = Field(default_factory=list)
    core_memory: list[str] = Field(default_factory=list)
    working_memory: list[str] = Field(default_factory=list)
    beliefs: list[str] = Field(default_factory=list)
    relationships: dict[str, str] = Field(default_factory=dict)
    resources: dict[str, int] = Field(default_factory=dict)
    location: str = "community"
    faction: str | None = None
    emotional_state: str = "calm"
