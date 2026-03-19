from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.models.world import WorldBlueprint, WorldMetrics


class SimulationStatus(str, Enum):
    GENERATING_WORLD = "generating_world"
    GENERATING_CITIZENS = "generating_citizens"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class SpeedMode(str, Enum):
    LIVE = "live"
    FAST_FORWARD = "fast_forward"
    JUMP = "jump"


class SimulationState(BaseModel):
    id: str
    status: SimulationStatus = SimulationStatus.GENERATING_WORLD
    speed_mode: SpeedMode = SpeedMode.LIVE
    rules_text: str = ""
    world_name: str = ""
    world_blueprint: WorldBlueprint | None = None
    agents_generated: int = 0
    agents_total: int = 25
    current_day: int = 0
    current_round: int = 0
    total_rounds: int = 0
    action_count: int = 0
    created_at: str = ""
    is_public: bool = False
    forked_from: str | None = None


class SSEEvent(BaseModel):
    type: Literal[
        "status",
        "world_ready",
        "citizen_generated",
        "round_complete",
        "narrative",
        "fast_forward_summary",
        "metrics_update",
        "injection_result",
        "simulation_complete",
        "error",
        "cancelled",
        "life_event",
        "demographics_loaded",
    ]
    data: dict[str, Any] = Field(default_factory=dict)


class ForkRequest(BaseModel):
    fork_at_day: int
    changes: str | None = None
