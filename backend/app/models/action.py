from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    SPEAK_PUBLIC = "SPEAK_PUBLIC"
    SPEAK_PRIVATE = "SPEAK_PRIVATE"
    TRADE = "TRADE"
    FORM_GROUP = "FORM_GROUP"
    PROPOSE_RULE = "PROPOSE_RULE"
    VOTE = "VOTE"
    PROTEST = "PROTEST"
    COMPLY = "COMPLY"
    DEFECT = "DEFECT"
    BUILD = "BUILD"
    OBSERVE = "OBSERVE"
    RECOMMEND = "RECOMMEND"
    PURCHASE = "PURCHASE"
    ABANDON = "ABANDON"
    COMPARE = "COMPARE"
    RESEARCH = "RESEARCH"
    INVESTIGATE = "INVESTIGATE"
    DO_NOTHING = "DO_NOTHING"


class AgentDecision(BaseModel):
    feel: str = ""
    want: str = ""
    fear: str = ""
    action: ActionType = ActionType.DO_NOTHING
    args: dict = Field(default_factory=dict)
    speech: str | None = None
    internal_thought: str = ""
    belief_updates: list[str] = Field(default_factory=list)
    memory_promotion: str | None = None


class ActionEntry(BaseModel):
    round: int
    day: int
    time_of_day: str
    agent_id: int
    agent_name: str
    location: str
    action_type: ActionType
    action_args: dict = Field(default_factory=dict)
    speech: str | None = None
    internal_thought: str | None = None
    targets: list[int] = Field(default_factory=list)
    world_state_changes: dict = Field(default_factory=dict)
    relationship_changes: dict = Field(default_factory=dict)


class ReactiveResponse(BaseModel):
    agent_id: int
    agent_name: str = ""
    reaction_type: Literal["respond", "whisper", "silent"] = "silent"
    content: str | None = None
    target_id: int | None = None
    location: str = ""
