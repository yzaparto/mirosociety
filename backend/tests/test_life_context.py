from app.models.agent import (
    AgentPersona, Personality, LifeState, FamilyMember,
    FormativeEvent, LifePressure,
)
from app.services.life_context import (
    compute_domain_level,
    compute_need_priority,
    compute_action_bias,
    find_relevant_echoes,
    build_life_prompt_block,
)


def _make_agent(**life_overrides) -> AgentPersona:
    ls_kwargs = dict(
        childhood_summary="Grew up in a small village.",
        formative_events=[],
        family=[],
    )
    ls_kwargs.update(life_overrides)
    return AgentPersona(
        id=1, name="Ada", role="Worker", age=30,
        personality=Personality(), background="test",
        life_state=LifeState(**ls_kwargs),
    )


def _make_agent_no_life() -> AgentPersona:
    return AgentPersona(
        id=2, name="Ghost", role="Wanderer", age=25,
        personality=Personality(), background="none",
    )


# ──────────────────────────────────────────────
# compute_domain_level
# ──────────────────────────────────────────────

def test_domain_level_desperate():
    result = compute_domain_level("finances", 0.1)
    assert "desperate" in result
    assert "survival" in result.lower()


def test_domain_level_struggling():
    result = compute_domain_level("health", 0.25)
    assert "struggling" in result


def test_domain_level_tight():
    result = compute_domain_level("career", 0.45)
    assert "tight but managing" in result


def test_domain_level_stable():
    result = compute_domain_level("finances", 0.6)
    assert "stable" in result


def test_domain_level_comfortable():
    result = compute_domain_level("health", 0.75)
    assert "comfortable" in result


def test_domain_level_thriving():
    result = compute_domain_level("career", 0.95)
    assert "thriving" in result


def test_domain_level_boundary_020():
    assert "desperate" in compute_domain_level("finances", 0.19)
    assert "struggling" in compute_domain_level("finances", 0.20)


def test_domain_level_unknown_domain():
    result = compute_domain_level("unknown", 0.1)
    assert result == "desperate"


# ──────────────────────────────────────────────
# compute_need_priority
# ──────────────────────────────────────────────

def test_need_priority_no_life_state():
    agent = _make_agent_no_life()
    assert compute_need_priority(agent, 10) == ""


def test_need_priority_urgent_pressure():
    agent = _make_agent(pressures=[
        LifePressure(domain="finances", description="Eviction", severity=0.8, deadline_day=11, created_day=1),
    ])
    result = compute_need_priority(agent, 10)
    assert "SURVIVAL MODE" in result
    assert "Eviction" in result


def test_need_priority_pressure_not_urgent_when_far():
    agent = _make_agent(pressures=[
        LifePressure(domain="finances", description="Rent", severity=0.9, deadline_day=20, created_day=1),
    ])
    result = compute_need_priority(agent, 10)
    assert "SURVIVAL MODE" not in result


def test_need_priority_pressure_not_urgent_low_severity():
    agent = _make_agent(pressures=[
        LifePressure(domain="finances", description="Rent", severity=0.4, deadline_day=11, created_day=1),
    ])
    result = compute_need_priority(agent, 10)
    assert "SURVIVAL MODE" not in result


def test_need_priority_basic_needs_finances():
    agent = _make_agent(finances=0.15)
    assert compute_need_priority(agent, 10) == "Your basic needs are threatened"


def test_need_priority_basic_needs_health():
    agent = _make_agent(health=0.1)
    assert compute_need_priority(agent, 10) == "Your basic needs are threatened"


def test_need_priority_family_dependency():
    agent = _make_agent(
        finances=0.35,
        family=[
            FamilyMember(name="Rosa", relation="daughter", age=5, dependency=0.8),
        ],
    )
    result = compute_need_priority(agent, 10)
    assert "depending on you" in result
    assert "Rosa" in result


def test_need_priority_career_stagnating():
    agent = _make_agent(career=0.25)
    assert compute_need_priority(agent, 10) == "Your career is stagnating"


def test_need_priority_all_high():
    agent = _make_agent(finances=0.8, career=0.8, health=0.9)
    assert "legacy" in compute_need_priority(agent, 10).lower()


def test_need_priority_default():
    agent = _make_agent(finances=0.5, career=0.5, health=0.5)
    assert compute_need_priority(agent, 10) == "Life is manageable but not easy"


# ──────────────────────────────────────────────
# compute_action_bias
# ──────────────────────────────────────────────

def test_action_bias_no_life_state():
    agent = _make_agent_no_life()
    assert compute_action_bias(agent, 10) == {}


def test_action_bias_financial_desperation():
    agent = _make_agent(finances=0.1)
    biases = compute_action_bias(agent, 10)
    assert "TRADE" in biases
    assert "NEED resources" in biases["TRADE"]
    assert "BUILD" in biases
    assert "afford" in biases["BUILD"]


def test_action_bias_financial_desperation_with_dependents():
    agent = _make_agent(
        finances=0.1,
        family=[FamilyMember(name="Tom", relation="son", age=3, dependency=0.9)],
    )
    biases = compute_action_bias(agent, 10)
    assert "family" in biases["DEFECT"].lower()


def test_action_bias_health_crisis():
    agent = _make_agent(health=0.15)
    biases = compute_action_bias(agent, 10)
    assert "energy" in biases["BUILD"].lower()
    assert "exhausted" in biases["PROTEST"].lower()
    assert "conserving" in biases["OBSERVE"].lower()


def test_action_bias_high_dependency():
    agent = _make_agent(
        family=[
            FamilyMember(name="A", relation="child", age=3, dependency=0.6),
            FamilyMember(name="B", relation="child", age=5, dependency=0.6),
        ],
    )
    biases = compute_action_bias(agent, 10)
    assert "DEFECT" in biases
    assert "safe" in biases["DEFECT"].lower()
    assert "PROTEST" in biases
    assert "counting on you" in biases["PROTEST"].lower()


def test_action_bias_career_pressure():
    agent = _make_agent(career=0.2)
    biases = compute_action_bias(agent, 10)
    assert "COMPLY" in biases
    assert "reliable" in biases["COMPLY"]


def test_action_bias_imminent_deadline():
    agent = _make_agent(pressures=[
        LifePressure(domain="finances", description="Debt payment", severity=0.7, deadline_day=11, created_day=1),
    ])
    biases = compute_action_bias(agent, 10)
    assert "DO_NOTHING" in biases
    assert "URGENT" in biases["DO_NOTHING"]
    assert "OBSERVE" in biases
    assert "deadline" in biases["OBSERVE"].lower()


def test_action_bias_thriving():
    agent = _make_agent(finances=0.85, career=0.8, health=0.9)
    biases = compute_action_bias(agent, 10)
    assert "PROPOSE_RULE" in biases
    assert "standing" in biases["PROPOSE_RULE"].lower()
    assert "BUILD" in biases
    assert "FORM_GROUP" in biases


def test_action_bias_empty_when_middle():
    agent = _make_agent(finances=0.5, career=0.5, health=0.5)
    biases = compute_action_bias(agent, 10)
    assert biases == {}


# ──────────────────────────────────────────────
# find_relevant_echoes
# ──────────────────────────────────────────────

def test_echoes_no_life_state():
    agent = _make_agent_no_life()
    assert find_relevant_echoes(agent, "new rule imposed") == []


def test_echoes_no_formative_events():
    agent = _make_agent()
    assert find_relevant_echoes(agent, "new rule imposed") == []


def test_echoes_authority_match():
    agent = _make_agent(formative_events=[
        FormativeEvent(
            age_at_event=10,
            description="Father was a strict law enforcer",
            lasting_effect="Reflexive obedience to authority",
        ),
    ])
    echoes = find_relevant_echoes(agent, "A new rule has been proposed by the leader")
    assert len(echoes) == 1
    assert "Echo from your past" in echoes[0]
    assert "Father" in echoes[0]


def test_echoes_scarcity_match():
    agent = _make_agent(formative_events=[
        FormativeEvent(
            age_at_event=8,
            description="Village faced a food crisis",
            lasting_effect="Hoards resources compulsively",
        ),
    ])
    echoes = find_relevant_echoes(agent, "There is a resource shortage in the market")
    assert len(echoes) >= 1
    assert "crisis" in echoes[0].lower() or "Hoards" in echoes[0]


def test_echoes_no_match():
    agent = _make_agent(formative_events=[
        FormativeEvent(
            age_at_event=12,
            description="Won a swimming contest",
            lasting_effect="Loves competition",
        ),
    ])
    assert find_relevant_echoes(agent, "The weather is nice today") == []


def test_echoes_max_two():
    agent = _make_agent(formative_events=[
        FormativeEvent(age_at_event=5, description="Saw a leader fall", lasting_effect="Distrusts order"),
        FormativeEvent(age_at_event=8, description="New rule destroyed home", lasting_effect="Hates authority"),
        FormativeEvent(age_at_event=12, description="Order restored peace", lasting_effect="Believes in law"),
    ])
    echoes = find_relevant_echoes(agent, "The leader proposed a new rule")
    assert len(echoes) <= 2


def test_echoes_trust_match():
    agent = _make_agent(formative_events=[
        FormativeEvent(
            age_at_event=15,
            description="Best friend betrayed a promise",
            lasting_effect="Slow to trust",
        ),
    ])
    echoes = find_relevant_echoes(agent, "Can you trust this person?")
    assert len(echoes) == 1


# ──────────────────────────────────────────────
# build_life_prompt_block
# ──────────────────────────────────────────────

def test_prompt_block_no_life_state():
    agent = _make_agent_no_life()
    assert build_life_prompt_block(agent, 10, "context") == ""


def test_prompt_block_contains_sections():
    agent = _make_agent()
    block = build_life_prompt_block(agent, 10, "context")
    assert "YOUR LIFE RIGHT NOW" in block
    assert "YOUR HISTORY" in block


def test_prompt_block_domain_levels():
    agent = _make_agent(finances=0.1, career=0.9, health=0.5)
    block = build_life_prompt_block(agent, 10, "context")
    assert "desperate" in block
    assert "thriving" in block
    assert "stable" in block.lower()


def test_prompt_block_family_listed():
    agent = _make_agent(family=[
        FamilyMember(name="Ella", relation="daughter", age=7, dependency=0.5),
    ])
    block = build_life_prompt_block(agent, 10, "context")
    assert "Ella" in block
    assert "daughter" in block


def test_prompt_block_pressures_listed():
    agent = _make_agent(pressures=[
        LifePressure(domain="health", description="Surgery needed", severity=0.9, deadline_day=15, created_day=1),
    ])
    block = build_life_prompt_block(agent, 10, "context")
    assert "Surgery needed" in block
    assert "severity 0.9" in block
    assert "deadline: day 15" in block


def test_prompt_block_childhood():
    agent = _make_agent()
    block = build_life_prompt_block(agent, 10, "context")
    assert "Grew up in a small village." in block


def test_prompt_block_formative_events():
    agent = _make_agent(formative_events=[
        FormativeEvent(age_at_event=7, description="Lost a parent", lasting_effect="Fear of abandonment"),
    ])
    block = build_life_prompt_block(agent, 10, "context")
    assert "Age 7" in block
    assert "Lost a parent" in block


def test_prompt_block_echoes_included():
    agent = _make_agent(formative_events=[
        FormativeEvent(
            age_at_event=10,
            description="Saw a leader betray the group",
            lasting_effect="Distrusts leaders",
        ),
    ])
    block = build_life_prompt_block(agent, 10, "A new leader has proposed a rule")
    assert "Echo from your past" in block


def test_prompt_block_all_domains_low():
    agent = _make_agent(
        finances=0.05, career=0.1, health=0.08,
        family=[FamilyMember(name="Kid", relation="child", age=2, dependency=0.9)],
        pressures=[
            LifePressure(domain="finances", description="Debt", severity=0.9, deadline_day=11, created_day=1),
        ],
    )
    block = build_life_prompt_block(agent, 10, "context")
    assert "SURVIVAL MODE" in block
    assert "desperate" in block


def test_prompt_block_all_domains_high():
    agent = _make_agent(finances=0.9, career=0.85, health=0.95)
    block = build_life_prompt_block(agent, 10, "context")
    assert "thriving" in block
    assert "legacy" in block.lower()
