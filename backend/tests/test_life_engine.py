"""Tests for the LifeEngine — probabilistic life events with cascading pressures."""
from __future__ import annotations

import asyncio
import random

import pytest

from app.models.agent import (
    AgentPersona, FamilyMember, LifePressure, LifeState, Personality,
)
from app.models.world import (
    WorldBlueprint, WorldState, Location, TimeConfig,
)
from app.services.life_engine import (
    EVAL_INTERVAL, MAX_EVENTS_PER_CYCLE, MAX_PRESSURES, LifeEngine,
)
from tests.conftest import MockLLM

pytestmark = pytest.mark.asyncio


def _make_life_state(**overrides) -> LifeState:
    defaults = dict(
        childhood_summary="Grew up in a small town.",
        finances=0.5,
        career=0.5,
        health=0.5,
        family=[
            FamilyMember(name="Rosa", relation="mother", age=55, dependency=0.3),
            FamilyMember(name="Leo", relation="brother", age=25, dependency=0.1),
        ],
    )
    defaults.update(overrides)
    return LifeState(**defaults)


def _make_agent(id: int = 1, name: str = "TestAgent", life_state: LifeState | None = None, **personality_kw) -> AgentPersona:
    p_defaults = dict(
        honesty=0.5, ambition=0.5, empathy=0.5,
        confrontational=0.5, conformity=0.5, brand_loyalty=0.5,
        price_sensitivity=0.5, social_proof=0.5, novelty_seeking=0.5,
    )
    p_defaults.update(personality_kw)
    return AgentPersona(
        id=id,
        name=name,
        role="worker",
        age=30,
        personality=Personality(**p_defaults),
        background=f"{name} is a worker.",
        life_state=life_state or _make_life_state(),
    )


def _make_world(day: int = 5) -> WorldState:
    bp = WorldBlueprint(
        name="Test World",
        description="A test world.",
        rules=["Rule 1"],
        locations=[Location(id="town", name="Town", type="public", description="A town")],
        resources=["money"],
        initial_tensions=["tension"],
        time_config=TimeConfig(total_days=30, rounds_per_day=3),
    )
    return WorldState(blueprint=bp, day=day)


def _engine() -> LifeEngine:
    return LifeEngine(llm=MockLLM())


# ============================================================================
# _tick_pressures
# ============================================================================

class TestTickPressures:
    def test_escalate_past_deadline(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(
            pressures=[
                LifePressure(domain="finances", description="Debt due", severity=0.5, deadline_day=3, created_day=1),
            ]
        ))
        engine._tick_pressures(agent, current_day=5)

        assert len(agent.life_state.pressures) == 1
        p = agent.life_state.pressures[0]
        assert p.severity == pytest.approx(0.7)
        assert p.deadline_day is None

    def test_resolve_when_domain_improved(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(
            finances=0.8,
            pressures=[
                LifePressure(domain="finances", description="Money trouble", severity=0.3, created_day=1),
            ]
        ))
        engine._tick_pressures(agent, current_day=5)

        assert len(agent.life_state.pressures) == 0
        assert any("Resolved" in entry for entry in agent.life_state.life_log)

    def test_decay_old_low_severity(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(
            pressures=[
                LifePressure(domain="health", description="Minor ache", severity=0.2, created_day=1),
            ]
        ))
        engine._tick_pressures(agent, current_day=25)

        assert len(agent.life_state.pressures) == 0

    def test_keeps_high_severity_old_pressure(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(
            pressures=[
                LifePressure(domain="health", description="Chronic issue", severity=0.6, created_day=1),
            ]
        ))
        engine._tick_pressures(agent, current_day=25)

        assert len(agent.life_state.pressures) == 1


# ============================================================================
# evaluate
# ============================================================================

class TestEvaluate:
    async def test_skips_non_interval_rounds(self):
        engine = _engine()
        agents = [_make_agent()]
        world = _make_world()
        results = await engine.evaluate(agents, world, round_num=3)
        assert results == []

    async def test_runs_on_interval_round(self):
        engine = _engine()
        agents = [_make_agent()]
        world = _make_world()
        results = await engine.evaluate(agents, world, round_num=EVAL_INTERVAL)
        assert isinstance(results, list)

    async def test_skips_agents_without_life_state(self):
        engine = _engine()
        agent = _make_agent()
        agent.life_state = None
        results = await engine.evaluate([agent], _make_world(), round_num=EVAL_INTERVAL)
        assert results == []

    async def test_respects_max_events_per_cycle(self):
        engine = _engine()
        agents = [_make_agent(id=i, name=f"Agent{i}", life_state=_make_life_state(finances=0.1)) for i in range(20)]
        world = _make_world()
        results = await engine.evaluate(agents, world, round_num=EVAL_INTERVAL)
        assert len(results) <= MAX_EVENTS_PER_CYCLE


# ============================================================================
# _select_event
# ============================================================================

class TestSelectEvent:
    def test_returns_event_for_struggling_agent(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.1, career=0.2, health=0.3))
        found = False
        for _ in range(30):
            evt = engine._select_event(agent)
            if evt is not None:
                found = True
                break
        assert found, "Expected at least one event to be selected for a struggling agent"

    def test_event_has_required_keys(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.1))
        evt = None
        for _ in range(30):
            evt = engine._select_event(agent)
            if evt is not None:
                break
        assert evt is not None
        assert "template" in evt
        assert "description" in evt
        assert "_domain" in evt

    def test_family_event_fills_placeholder(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.5))
        found = False
        for _ in range(200):
            evt = engine._select_event(agent)
            if evt and evt["_domain"] == "family" and evt.get("pressure"):
                assert "{family_member}" not in evt["pressure"]
                found = True
                break
        if not found:
            pytest.skip("Family event with pressure not drawn in 200 tries")


# ============================================================================
# _apply_event
# ============================================================================

class TestApplyEvent:
    def test_applies_domain_delta(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.5))

        event = {
            "template": "unexpected_expense",
            "description": "A major unexpected expense hits",
            "domain_delta": -0.2,
            "pressure": "Must cover urgent costs",
            "weight_factors": {},
            "_domain": "finances",
            "_polarity": "negative",
        }
        engine._apply_event(agent, event, current_day=5)
        assert agent.life_state.finances == pytest.approx(0.3)

    def test_clamps_domain_at_zero(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.1))

        event = {
            "template": "theft_or_loss",
            "description": "Resources stolen or lost",
            "domain_delta": -0.25,
            "pressure": "Lost significant resources",
            "weight_factors": {},
            "_domain": "finances",
            "_polarity": "negative",
        }
        engine._apply_event(agent, event, current_day=5)
        assert agent.life_state.finances == pytest.approx(0.0)

    def test_respects_max_pressures_cap(self):
        engine = _engine()
        existing = [
            LifePressure(domain="finances", description=f"P{i}", severity=0.5, created_day=1)
            for i in range(MAX_PRESSURES)
        ]
        agent = _make_agent(life_state=_make_life_state(pressures=existing))

        event = {
            "template": "debt_called_in",
            "description": "An old debt comes due",
            "domain_delta": -0.15,
            "pressure": "Creditor demands repayment",
            "weight_factors": {},
            "_domain": "finances",
            "_polarity": "negative",
        }
        engine._apply_event(agent, event, current_day=5)
        assert len(agent.life_state.pressures) == MAX_PRESSURES

    def test_adds_to_life_log(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state())

        event = {
            "template": "windfall",
            "description": "An unexpected financial gain",
            "domain_delta": 0.2,
            "pressure": None,
            "weight_factors": {},
            "_domain": "finances",
            "_polarity": "positive",
        }
        engine._apply_event(agent, event, current_day=7)
        assert any("Day 7" in entry for entry in agent.life_state.life_log)

    def test_family_event_no_domain_delta(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(health=0.5))

        event = {
            "template": "family_milestone",
            "description": "A family celebration",
            "domain_delta": None,
            "pressure": None,
            "weight_factors": {},
            "_domain": "family",
            "_polarity": "positive",
        }
        engine._apply_event(agent, event, current_day=5)
        assert agent.life_state.health == pytest.approx(0.5)
        assert agent.life_state.finances == pytest.approx(0.5)
        assert agent.life_state.career == pytest.approx(0.5)


# ============================================================================
# _apply_cascades
# ============================================================================

class TestApplyCascades:
    def test_job_threat_cascades_when_finances_low(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.3))

        engine._apply_cascades(agent, "job_threat", current_day=5)
        assert agent.life_state.finances == pytest.approx(0.2)
        assert any("money" in p.description.lower() or "work" in p.description.lower() for p in agent.life_state.pressures)

    def test_job_threat_no_cascade_when_finances_ok(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state(finances=0.6))

        engine._apply_cascades(agent, "job_threat", current_day=5)
        assert agent.life_state.finances == pytest.approx(0.6)
        assert len(agent.life_state.pressures) == 0

    def test_family_illness_cascades_with_dependent(self):
        engine = _engine()
        agent = _make_agent(
            empathy=0.8,
            life_state=_make_life_state(
                family=[FamilyMember(name="Rosa", relation="mother", age=60, dependency=0.7)],
            ),
        )

        engine._apply_cascades(agent, "family_illness", current_day=5)
        assert agent.life_state.finances == pytest.approx(0.45)
        assert agent.life_state.health == pytest.approx(0.4)
        assert len(agent.life_state.pressures) == 2

    def test_family_illness_no_cascade_without_dependent(self):
        engine = _engine()
        agent = _make_agent(
            empathy=0.3,
            life_state=_make_life_state(
                family=[FamilyMember(name="Leo", relation="brother", age=25, dependency=0.1)],
            ),
        )

        engine._apply_cascades(agent, "family_illness", current_day=5)
        assert agent.life_state.finances == pytest.approx(0.5)
        assert agent.life_state.health == pytest.approx(0.5)
        assert len(agent.life_state.pressures) == 0

    def test_no_cascade_for_unknown_template(self):
        engine = _engine()
        agent = _make_agent(life_state=_make_life_state())

        engine._apply_cascades(agent, "nonexistent_event", current_day=5)
        assert agent.life_state.finances == pytest.approx(0.5)
        assert len(agent.life_state.pressures) == 0

    def test_cascade_respects_max_pressures(self):
        engine = _engine()
        existing = [
            LifePressure(domain="finances", description=f"P{i}", severity=0.5, created_day=1)
            for i in range(MAX_PRESSURES)
        ]
        agent = _make_agent(life_state=_make_life_state(finances=0.2, pressures=existing))

        engine._apply_cascades(agent, "job_threat", current_day=5)
        assert len(agent.life_state.pressures) == MAX_PRESSURES
