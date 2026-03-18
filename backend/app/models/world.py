from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class Location(BaseModel):
    id: str
    name: str
    type: Literal["public", "commerce", "governance", "residential", "social"]
    description: str


class TimeConfig(BaseModel):
    total_days: int = 365
    rounds_per_day: int = 3
    active_agents_per_round_min: int = 3
    active_agents_per_round_max: int = 10


class WorldBlueprint(BaseModel):
    name: str
    description: str
    rules: list[str]
    locations: list[Location]
    resources: list[str]
    initial_tensions: list[str]
    time_config: TimeConfig


class WorldMetrics(BaseModel):
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    prosperity: float = Field(default=0.5, ge=0.0, le=1.0)
    trust: float = Field(default=0.5, ge=0.0, le=1.0)
    freedom: float = Field(default=0.5, ge=0.0, le=1.0)
    conflict: float = Field(default=0.2, ge=0.0, le=1.0)
    brand_sentiment: float = Field(default=0.5, ge=0.0, le=1.0)
    purchase_intent: float = Field(default=0.5, ge=0.0, le=1.0)
    word_of_mouth: float = Field(default=0.0, ge=0.0, le=1.0)
    churn_risk: float = Field(default=0.2, ge=0.0, le=1.0)
    adoption_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class Institution(BaseModel):
    name: str
    purpose: str
    founder_id: int
    member_ids: list[int] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    created_day: int = 0


class Proposal(BaseModel):
    id: str
    proposer_id: int
    content: str
    votes_for: list[int] = Field(default_factory=list)
    votes_against: list[int] = Field(default_factory=list)
    status: Literal["open", "passed", "rejected"] = "open"
    created_round: int = 0


class WorldState(BaseModel):
    blueprint: WorldBlueprint
    metrics: WorldMetrics = Field(default_factory=WorldMetrics)
    institutions: list[Institution] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    day: int = 1
    round_in_day: int = 0
    active_disputes: list[str] = Field(default_factory=list)
    community_rules: list[str] = Field(default_factory=list)
