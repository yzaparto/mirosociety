import pytest
from unittest.mock import AsyncMock
from app.models.agent import (
    AgentPersona, Personality, LifeState, FamilyMember,
    FormativeEvent, LifePressure,
)
from app.models.world import WorldBlueprint, TimeConfig
from app.services.citizen_generator import CitizenGenerator


def _make_blueprint():
    return WorldBlueprint(
        name="TestWorld", description="A test world", rules=["Be honest"],
        locations=[], resources=["goods", "money"], initial_tensions=["inequality"],
        time_config=TimeConfig(total_days=30),
    )


def _make_agent(id=0, age=35, ambition=0.7, conformity=0.3):
    return AgentPersona(
        id=id, name=f"Agent{id}", role="Worker", age=age,
        personality=Personality(ambition=ambition, conformity=conformity),
        background="A hard worker", goals=["Survive"],
        beliefs=["The system is unfair"],
    )


def test_apply_trait_modifiers_single_event():
    gen = CitizenGenerator(llm=AsyncMock())
    agent = _make_agent(ambition=0.5)
    agent.life_state = LifeState(
        childhood_summary="test",
        formative_events=[
            FormativeEvent(
                age_at_event=10, description="test",
                lasting_effect="test",
                trait_modifier={"ambition": 0.15},
            ),
        ],
        family=[],
    )
    gen._apply_trait_modifiers(agent)
    assert agent.personality.ambition == pytest.approx(0.65, abs=0.01)


def test_apply_trait_modifiers_damping():
    gen = CitizenGenerator(llm=AsyncMock())
    agent = _make_agent(conformity=0.5)
    agent.life_state = LifeState(
        childhood_summary="test",
        formative_events=[
            FormativeEvent(age_at_event=7, description="e1", lasting_effect="e1",
                           trait_modifier={"conformity": -0.15}),
            FormativeEvent(age_at_event=14, description="e2", lasting_effect="e2",
                           trait_modifier={"conformity": -0.15}),
            FormativeEvent(age_at_event=20, description="e3", lasting_effect="e3",
                           trait_modifier={"conformity": -0.15}),
        ],
        family=[],
    )
    gen._apply_trait_modifiers(agent)
    # 1st: -0.15 * 1.0 = -0.15 → 0.35
    # 2nd: -0.15 * 0.667 = -0.10 → 0.25
    # 3rd: -0.15 * 0.5 = -0.075 → 0.175
    assert agent.personality.conformity >= 0.0
    assert agent.personality.conformity < 0.35
    assert agent.personality.conformity == pytest.approx(0.175, abs=0.02)


def test_enforce_life_diversity_finances():
    gen = CitizenGenerator(llm=AsyncMock())
    agents = []
    for i in range(20):
        a = _make_agent(id=i)
        a.life_state = LifeState(childhood_summary="test", finances=0.2, family=[])
        agents.append(a)
    gen._enforce_life_diversity(agents)
    avg = sum(a.life_state.finances for a in agents) / len(agents)
    assert avg > 0.3


def test_num_formative_events_by_age():
    gen = CitizenGenerator(llm=AsyncMock())
    assert gen._num_formative_events(25) == 4
    assert gen._num_formative_events(40) == 5
    assert gen._num_formative_events(60) == 6


def test_parse_life_history_complete():
    gen = CitizenGenerator(llm=AsyncMock())
    agent = _make_agent()
    data = {
        "childhood_summary": "Grew up on a farm in rural Kansas.",
        "formative_events": [
            {
                "age_at_event": 8,
                "description": "Watched the family barn burn down.",
                "lasting_effect": "Fears losing what was built",
                "trait_modifier": {"conformity": 0.1, "ambition": 0.05},
            },
        ],
        "family": [
            {
                "name": "Martha",
                "relation": "spouse",
                "age": 33,
                "status": "healthy",
                "dependency": 0.1,
                "bond_strength": 0.9,
            },
        ],
        "finances": 0.6,
        "career": 0.7,
        "health": 0.85,
        "initial_pressures": [
            {
                "domain": "finances",
                "description": "Roof needs repair before winter.",
                "severity": 0.5,
            },
        ],
    }
    life = gen._parse_life_history(data, agent)
    assert life.childhood_summary == "Grew up on a farm in rural Kansas."
    assert len(life.formative_events) == 1
    assert life.formative_events[0].age_at_event == 8
    assert life.formative_events[0].trait_modifier["conformity"] == 0.1
    assert len(life.family) == 1
    assert life.family[0].name == "Martha"
    assert life.finances == 0.6
    assert life.career == 0.7
    assert life.health == 0.85
    assert len(life.pressures) == 1
    assert life.pressures[0].domain == "finances"


def test_parse_life_history_missing_fields():
    gen = CitizenGenerator(llm=AsyncMock())
    agent = _make_agent()
    data = {}
    life = gen._parse_life_history(data, agent)
    assert life.childhood_summary != ""
    assert life.formative_events == []
    assert life.family == []
    assert life.finances == 0.5
    assert life.career == 0.5
    assert life.health == 0.5
    assert life.pressures == []
