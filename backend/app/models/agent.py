from __future__ import annotations
from pydantic import BaseModel, Field


class SocialEdge(BaseModel):
    target_id: int
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)


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


COMMUNICATION_STYLES = {
    "terse": "You speak in short, blunt sentences. 5-10 words max. No pleasantries. 'Cancelled. Moving on.'",
    "sarcastic": "You use irony and dry humor. You rarely say what you mean directly. 'Oh great, another price hike. What a surprise.'",
    "verbose": "You over-explain. You use qualifiers, caveats, and parentheticals. You think out loud.",
    "question-asker": "You respond to statements with questions. You probe rather than declare. 'But have you actually looked at the alternatives?'",
    "anecdote-teller": "You relate everything to personal stories. 'This reminds me of when Blockbuster...'",
    "data-driven": "You cite numbers, comparisons, facts. You distrust emotional arguments. 'The math doesn't work out.'",
    "emotional": "You lead with feelings. Exclamation marks, dramatic phrasing, personal impact.",
    "passive-aggressive": "You agree on the surface but undermine subtly. 'Sure, if that works for you...'",
}


class FamilyMember(BaseModel):
    name: str
    relation: str
    age: int
    status: str = "healthy"
    dependency: float = Field(default=0.0, ge=0.0, le=1.0)
    bond_strength: float = Field(default=0.7, ge=0.0, le=1.0)


class FormativeEvent(BaseModel):
    age_at_event: int
    description: str
    lasting_effect: str
    trait_modifier: dict[str, float] = Field(default_factory=dict)


class LifePressure(BaseModel):
    domain: str
    description: str
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    deadline_day: int | None = None
    created_day: int = 0


class LifeState(BaseModel):
    childhood_summary: str
    formative_events: list[FormativeEvent] = Field(default_factory=list)
    family: list[FamilyMember] = Field(default_factory=list)
    finances: float = Field(default=0.5, ge=0.0, le=1.0)
    career: float = Field(default=0.5, ge=0.0, le=1.0)
    health: float = Field(default=0.5, ge=0.0, le=1.0)
    pressures: list[LifePressure] = Field(default_factory=list)
    life_log: list[str] = Field(default_factory=list)


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
    social_connections: list[SocialEdge] = Field(default_factory=list)
    communication_style: str = Field(default="emotional")
    knowledge_level: str = Field(default="full")
    life_state: LifeState | None = None
