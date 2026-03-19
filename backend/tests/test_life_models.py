from app.models.agent import (
    AgentPersona, Personality, LifeState, FamilyMember,
    FormativeEvent, LifePressure,
)


def test_life_state_defaults():
    ls = LifeState(childhood_summary="Grew up on a farm.", formative_events=[], family=[])
    assert ls.finances == 0.5
    assert ls.career == 0.5
    assert ls.health == 0.5
    assert ls.pressures == []
    assert ls.life_log == []


def test_family_member():
    fm = FamilyMember(name="Maria", relation="spouse", age=34, status="healthy", dependency=0.2)
    assert fm.bond_strength == 0.7


def test_formative_event_trait_modifier():
    fe = FormativeEvent(
        age_at_event=7,
        description="Parents divorced",
        lasting_effect="Distrusts commitment",
        trait_modifier={"conformity": -0.1, "empathy": 0.15},
    )
    assert fe.trait_modifier["conformity"] == -0.1


def test_life_pressure_no_deadline():
    lp = LifePressure(domain="finances", description="Rent overdue", severity=0.6, created_day=1)
    assert lp.deadline_day is None


def test_life_pressure_with_deadline():
    lp = LifePressure(domain="finances", description="Rent overdue", severity=0.6, deadline_day=15, created_day=1)
    assert lp.deadline_day == 15


def test_agent_persona_has_life_state():
    ls = LifeState(childhood_summary="test", formative_events=[], family=[])
    agent = AgentPersona(
        id=0, name="Test", role="Worker", age=30,
        personality=Personality(), background="test",
        life_state=ls,
    )
    assert agent.life_state.finances == 0.5
    assert agent.life_state.childhood_summary == "test"


def test_agent_persona_optional_life_state():
    agent = AgentPersona(
        id=0, name="Test", role="Worker", age=30,
        personality=Personality(), background="test",
    )
    assert agent.life_state is None
