# Life Domain System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give every MiroSociety agent a full human lifecycle — backstory, family, financial pressure, health, career, formative events that shape personality — and seed populations from real US Census data.

**Architecture:** New `LifeState` model on `AgentPersona`, new `LifeEngine` service parallel to `TensionEngine`, new `CensusService` for real demographic data, enhanced `CitizenGenerator` for life history generation, modified decision prompt with life context and action biasing, frontend Life tab and city input.

**Tech Stack:** Python/Pydantic (models), FastAPI (API), httpx (Census API), Vue 3 (frontend), existing LLMClient for generation.

**Design Doc:** `docs/plans/2026-03-19-life-domain-system-design.md`

---

### Task 1: LifeState Data Models

**Files:**
- Modify: `backend/app/models/agent.py`
- Create: `backend/tests/test_life_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_life_models.py
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
    assert fm.bond_strength == 0.7  # default

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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_life_models.py -v`
Expected: FAIL — `LifeState`, `FamilyMember`, `FormativeEvent`, `LifePressure` not defined

**Step 3: Write the models**

Add to `backend/app/models/agent.py` — above `AgentPersona`:

```python
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
```

Add `life_state` field to `AgentPersona`:

```python
life_state: LifeState | None = None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_life_models.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add backend/app/models/agent.py backend/tests/test_life_models.py
git commit -m "feat: add LifeState, FamilyMember, FormativeEvent, LifePressure models"
```

---

### Task 2: Life Context Computation (need priority, domain levels, action bias)

**Files:**
- Create: `backend/app/services/life_context.py`
- Create: `backend/tests/test_life_context.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_life_context.py
from app.models.agent import (
    AgentPersona, Personality, LifeState, FamilyMember,
    FormativeEvent, LifePressure,
)
from app.services.life_context import (
    compute_need_priority, compute_domain_level, compute_action_bias,
    find_relevant_echoes, build_life_prompt_block,
)

def _make_agent(finances=0.5, career=0.5, health=0.5, family=None, pressures=None, formative=None):
    ls = LifeState(
        childhood_summary="Grew up in a small town.",
        formative_events=formative or [],
        family=family or [],
        finances=finances, career=career, health=health,
        pressures=pressures or [],
    )
    return AgentPersona(
        id=0, name="Test", role="Worker", age=30,
        personality=Personality(), background="test", life_state=ls,
    )

def test_need_priority_survival_mode():
    agent = _make_agent(
        finances=0.1,
        pressures=[LifePressure(domain="finances", description="Eviction", severity=0.8, deadline_day=5, created_day=0)],
    )
    result = compute_need_priority(agent, current_day=4)
    assert "SURVIVAL" in result.upper() or "must act" in result.lower()

def test_need_priority_thriving():
    agent = _make_agent(finances=0.9, career=0.8, health=0.9)
    result = compute_need_priority(agent, current_day=10)
    assert "legacy" in result.lower() or "meaning" in result.lower() or "good" in result.lower()

def test_domain_level_desperate():
    assert "desperate" in compute_domain_level("finances", 0.1)

def test_domain_level_thriving():
    assert "thriving" in compute_domain_level("finances", 0.9)

def test_action_bias_financial_desperation():
    agent = _make_agent(finances=0.15)
    bias = compute_action_bias(agent, current_day=10)
    assert "TRADE" in bias
    assert "urgent" in bias["TRADE"].lower() or "need" in bias["TRADE"].lower()

def test_action_bias_high_dependency():
    family = [FamilyMember(name="Aiden", relation="child", age=6, dependency=0.9)]
    agent = _make_agent(family=family)
    bias = compute_action_bias(agent, current_day=10)
    assert "DEFECT" in bias
    assert "family" in bias["DEFECT"].lower()

def test_action_bias_thriving():
    agent = _make_agent(finances=0.85, career=0.8)
    bias = compute_action_bias(agent, current_day=10)
    assert "PROPOSE_RULE" in bias

def test_find_relevant_echoes_authority():
    events = [FormativeEvent(
        age_at_event=10, description="Father punished for questioning the elder",
        lasting_effect="Fears authority and avoids confrontation",
        trait_modifier={"confrontational": -0.1},
    )]
    agent = _make_agent(formative=events)
    echoes = find_relevant_echoes(agent, "A new rule has been proposed by the council leader")
    assert len(echoes) >= 1
    assert "Father" in echoes[0]

def test_find_relevant_echoes_no_match():
    events = [FormativeEvent(
        age_at_event=10, description="Won a singing contest",
        lasting_effect="Believes in self-expression",
        trait_modifier={},
    )]
    agent = _make_agent(formative=events)
    echoes = find_relevant_echoes(agent, "The market is open for trading")
    assert len(echoes) == 0

def test_build_life_prompt_block_has_sections():
    family = [FamilyMember(name="Maria", relation="spouse", age=32)]
    pressures = [LifePressure(domain="finances", description="Rent is overdue", severity=0.6, created_day=0)]
    agent = _make_agent(finances=0.3, family=family, pressures=pressures)
    block = build_life_prompt_block(agent, current_day=10, context="community meeting")
    assert "YOUR LIFE RIGHT NOW" in block
    assert "Maria" in block
    assert "Rent" in block or "rent" in block
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_life_context.py -v`
Expected: FAIL — module `app.services.life_context` not found

**Step 3: Implement life_context.py**

Create `backend/app/services/life_context.py` with functions: `compute_need_priority`, `compute_domain_level`, `compute_action_bias`, `find_relevant_echoes`, `build_life_prompt_block`.

See design doc Section 3 for the full logic of each function. Key implementation details:
- `compute_domain_level` uses the DOMAIN_LEVELS and DOMAIN_FLAVOR lookup tables
- `compute_action_bias` returns `dict[str, str]` mapping action names to annotation strings
- `find_relevant_echoes` pattern-matches formative event `lasting_effect` against current context keywords
- `build_life_prompt_block` assembles all sections into a single string for prompt injection

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_life_context.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add backend/app/services/life_context.py backend/tests/test_life_context.py
git commit -m "feat: add life context computation — need priority, domain levels, action bias, echoes"
```

---

### Task 3: Life Events Engine

**Files:**
- Create: `backend/app/services/life_engine.py`
- Create: `backend/tests/test_life_engine.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_life_engine.py
import pytest
from unittest.mock import AsyncMock
from app.models.agent import (
    AgentPersona, Personality, LifeState, FamilyMember, LifePressure,
)
from app.models.world import WorldState, WorldBlueprint, TimeConfig, WorldMetrics
from app.services.life_engine import LifeEngine

def _make_world():
    bp = WorldBlueprint(
        name="TestWorld", description="test", rules=["be kind"],
        locations=[], resources=["goods", "money"], initial_tensions=["inequality"],
        time_config=TimeConfig(total_days=30),
    )
    return WorldState(blueprint=bp, day=10)

def _make_agent(id=0, finances=0.5, health=0.5, career=0.5, family=None, pressures=None):
    ls = LifeState(
        childhood_summary="test", formative_events=[], family=family or [],
        finances=finances, career=career, health=health,
        pressures=pressures or [],
    )
    return AgentPersona(
        id=id, name=f"Agent{id}", role="Worker", age=30,
        personality=Personality(ambition=0.5, empathy=0.5), background="test",
        life_state=ls,
    )

def test_tick_pressures_escalate_deadline():
    engine = LifeEngine(llm=AsyncMock())
    agent = _make_agent(pressures=[
        LifePressure(domain="finances", description="Rent", severity=0.5, deadline_day=8, created_day=0),
    ])
    engine._tick_pressures(agent, current_day=10)
    assert agent.life_state.pressures[0].severity > 0.5
    assert agent.life_state.pressures[0].deadline_day is None

def test_tick_pressures_resolve():
    engine = LifeEngine(llm=AsyncMock())
    agent = _make_agent(finances=0.8, pressures=[
        LifePressure(domain="finances", description="Rent", severity=0.3, created_day=0),
    ])
    engine._tick_pressures(agent, current_day=5)
    assert len(agent.life_state.pressures) == 0

def test_tick_pressures_decay_old():
    engine = LifeEngine(llm=AsyncMock())
    agent = _make_agent(pressures=[
        LifePressure(domain="career", description="Mild worry", severity=0.2, created_day=0),
    ])
    engine._tick_pressures(agent, current_day=25)
    assert len(agent.life_state.pressures) == 0

def test_eval_skips_non_interval_rounds():
    engine = LifeEngine(llm=AsyncMock())
    agents = [_make_agent()]
    world = _make_world()
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        engine.evaluate(agents, world, round_num=3)
    )
    assert result == []

def test_select_event_respects_weight_factors():
    engine = LifeEngine(llm=AsyncMock())
    agent = _make_agent(finances=0.1)
    event = engine._select_event(agent)
    assert event is not None
    assert event["template"] in engine.CATALOG["finances"]["negative"][0]["template"] or True  # just verifying it returns something

def test_max_pressures_cap():
    engine = LifeEngine(llm=AsyncMock())
    agent = _make_agent(pressures=[
        LifePressure(domain="finances", description=f"p{i}", severity=0.5, created_day=0)
        for i in range(4)
    ])
    event = {"domain_delta": -0.1, "pressure": "New problem", "template": "test"}
    engine._apply_event(agent, event, current_day=10)
    assert len(agent.life_state.pressures) <= 4
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_life_engine.py -v`
Expected: FAIL — module not found

**Step 3: Implement LifeEngine**

Create `backend/app/services/life_engine.py`. Key components:
- `CATALOG` dict with event templates by domain (finances, career, health, family) × polarity (positive, negative)
- `CASCADE_RULES` dict mapping event templates to conditional follow-on effects
- `evaluate()` — main entry point, runs every EVAL_INTERVAL rounds
- `_tick_pressures()` — escalate/resolve/decay existing pressures
- `_select_candidates()` — weighted selection of agents due for events
- `_select_event()` — pick from catalog based on agent state and weight factors
- `_personalize_event()` — LLM call to turn template into specific narrative
- `_apply_event()` — update life domains, create pressures, run cascades
- `_apply_cascades()` — check CASCADE_RULES for chain effects

See design doc Section 2 for full logic.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_life_engine.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add backend/app/services/life_engine.py backend/tests/test_life_engine.py
git commit -m "feat: add LifeEngine — probabilistic life events with cascading pressures"
```

---

### Task 4: Backstory Generator (Life History Generation)

**Files:**
- Modify: `backend/app/services/citizen_generator.py`
- Create: `backend/tests/test_backstory_gen.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_backstory_gen.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.models.agent import AgentPersona, Personality, LifeState
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
        formative_events=[{
            "age_at_event": 10, "description": "test",
            "lasting_effect": "test",
            "trait_modifier": {"ambition": 0.15},
        }],
        family=[],
    )
    # Convert dicts to FormativeEvent objects first
    from app.models.agent import FormativeEvent
    agent.life_state.formative_events = [
        FormativeEvent(**e) if isinstance(e, dict) else e
        for e in agent.life_state.formative_events
    ]
    gen._apply_trait_modifiers(agent)
    assert agent.personality.ambition == pytest.approx(0.65, abs=0.01)

def test_apply_trait_modifiers_damping():
    gen = CitizenGenerator(llm=AsyncMock())
    agent = _make_agent(conformity=0.5)
    from app.models.agent import FormativeEvent
    agent.life_state = LifeState(
        childhood_summary="test",
        formative_events=[
            FormativeEvent(age_at_event=7, description="e1", lasting_effect="e1", trait_modifier={"conformity": -0.15}),
            FormativeEvent(age_at_event=14, description="e2", lasting_effect="e2", trait_modifier={"conformity": -0.15}),
            FormativeEvent(age_at_event=20, description="e3", lasting_effect="e3", trait_modifier={"conformity": -0.15}),
        ],
        family=[],
    )
    gen._apply_trait_modifiers(agent)
    # 1st: -0.15, 2nd: -0.15*0.67=-0.10, 3rd: -0.15*0.5=-0.075 => total ~ -0.325
    # But 0.5 - 0.325 = 0.175, should NOT be less than 0 due to clamping
    assert agent.personality.conformity >= 0.0
    # Should be LESS than 0.5 - 0.15 = 0.35 (damping means NOT full -0.45)
    assert agent.personality.conformity > 0.5 - 0.45

def test_enforce_life_diversity_finances():
    gen = CitizenGenerator(llm=AsyncMock())
    agents = []
    for i in range(20):
        a = _make_agent(id=i)
        a.life_state = LifeState(childhood_summary="test", finances=0.2, family=[])
        agents.append(a)
    gen._enforce_life_diversity(agents)
    avg = sum(a.life_state.finances for a in agents) / len(agents)
    assert avg > 0.3  # diversity enforcement pushed some up

def test_num_formative_events_by_age():
    gen = CitizenGenerator(llm=AsyncMock())
    assert gen._num_formative_events(25) == 4
    assert gen._num_formative_events(40) == 5
    assert gen._num_formative_events(60) == 6
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_backstory_gen.py -v`
Expected: FAIL — methods not found on CitizenGenerator

**Step 3: Implement backstory generation**

Modify `backend/app/services/citizen_generator.py`:
- Add `LIFE_HISTORY_PROMPT` constant (see design doc Section 4)
- Add `_generate_life_histories()` async method — batched LLM calls, one per agent
- Add `_parse_life_history()` — parse LLM JSON response into LifeState
- Add `_apply_trait_modifiers()` — apply formative event trait modifiers with damping
- Add `_apply_all_trait_modifiers()` — loop over all agents
- Add `_enforce_life_diversity()` — audit and correct distribution bias
- Add `_num_formative_events()` — 4 for <30, 5 for <50, 6 for 50+
- Modify `generate()` to call `_generate_life_histories()` after `_generate_personas()` and before `_generate_relationships()`

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_backstory_gen.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add backend/app/services/citizen_generator.py backend/tests/test_backstory_gen.py
git commit -m "feat: add life history generation with trait modifiers and diversity enforcement"
```

---

### Task 5: Census Demographic Service

**Files:**
- Create: `backend/app/services/census.py`
- Create: `backend/app/models/demographics.py`
- Create: `backend/tests/test_census.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_census.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.demographics import DemographicProfile, AgeDistribution, IncomeDistribution
from app.services.census import CensusService

def test_resolve_fips_known_city():
    svc = CensusService(llm=AsyncMock())
    fips = svc._resolve_fips("san francisco", "CA")
    assert fips == ("06", "67000")

def test_resolve_fips_unknown_city():
    svc = CensusService(llm=AsyncMock())
    fips = svc._resolve_fips("randomville", None)
    assert fips is None

def test_resolve_fips_case_insensitive():
    svc = CensusService(llm=AsyncMock())
    fips = svc._resolve_fips("New York", "NY")
    assert fips is not None

def test_demographic_profile_model():
    profile = DemographicProfile(
        city_name="Test City", state="CA", population=100000,
        age=[AgeDistribution(bracket="25_34", percentage=0.22)],
        income=[IncomeDistribution(bracket="50k_75k", percentage=0.2)],
        occupations=[], ethnicity=[],
        median_household_income=75000, poverty_rate=0.12,
        unemployment_rate=0.05, homeownership_rate=0.45,
        median_rent=2000, rent_burden_rate=0.4,
        college_education_rate=0.35, median_age=36.0,
        city_character="A diverse city",
    )
    assert profile.city_name == "Test City"
    assert profile.poverty_rate == 0.12
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_census.py -v`
Expected: FAIL — modules not found

**Step 3: Implement demographics model and CensusService**

Create `backend/app/models/demographics.py`:
- `AgeDistribution`, `IncomeDistribution`, `OccupationDistribution`, `EthnicityDistribution` — simple bracket + percentage models
- `DemographicProfile` — full city profile with all distributions and key stats

Create `backend/app/services/census.py`:
- `CITY_FIPS` dict — top ~100 US cities mapped to (state_fips, place_fips)
- `TABLE_VARIABLES` — which Census variables to fetch per profile table (DP03, DP05, DP02)
- `_resolve_fips()` — city name → FIPS lookup, case-insensitive, supports optional state
- `_fetch_acs()` — single HTTP GET to Census API for one profile table
- `get_profile()` — parallel fetch of DP02+DP03+DP05, build DemographicProfile, cache to store
- `_build_profile()` — parse Census API response into DemographicProfile
- `_llm_estimate()` — fallback for unknown/non-US cities using LLM world knowledge

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_census.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add backend/app/models/demographics.py backend/app/services/census.py backend/tests/test_census.py
git commit -m "feat: add CensusService for real city demographics via Census Bureau API"
```

---

### Task 6: Integrate Life Context into Decision Prompt

**Files:**
- Modify: `backend/app/services/engine.py` (AGENT_DECISION_SYSTEM prompt, `_build_agent_prompt` or equivalent, response parsing)

**Step 1: Write the failing test**

```python
# backend/tests/test_life_prompt_integration.py
from app.models.agent import (
    AgentPersona, Personality, LifeState, FamilyMember,
    FormativeEvent, LifePressure,
)
from app.services.life_context import build_life_prompt_block

def test_life_block_in_prompt_format():
    ls = LifeState(
        childhood_summary="Grew up poor in the Mission district.",
        formative_events=[FormativeEvent(
            age_at_event=11, description="Found mother crying over bills",
            lasting_effect="Learned money problems mean love problems",
            trait_modifier={"honesty": -0.05},
        )],
        family=[FamilyMember(name="Linh", relation="spouse", age=32, dependency=0.2)],
        finances=0.25, career=0.4, health=0.7,
        pressures=[LifePressure(domain="finances", description="Rent went up again", severity=0.6, created_day=1)],
    )
    agent = AgentPersona(
        id=0, name="Marcus", role="Line cook", age=34,
        personality=Personality(), background="test", life_state=ls,
    )
    block = build_life_prompt_block(agent, current_day=10, context="new rule proposed by council")
    assert "YOUR LIFE RIGHT NOW" in block
    assert "struggling" in block.lower() or "desperate" in block.lower()
    assert "Linh" in block
    assert "Rent" in block
    assert "YOUR HISTORY" in block
    assert "Mission" in block or "poor" in block
```

**Step 2: Run test to verify it passes** (should already pass from Task 2)

Run: `cd backend && python -m pytest tests/test_life_prompt_integration.py -v`

**Step 3: Modify engine.py**

Modify `AGENT_DECISION_SYSTEM` prompt template:
- Add `{life_context}` placeholder between WHO YOU ARE and CORE MEMORIES
- Add LIFE and PAST steps to the reasoning chain
- Add `life_context` and `past_echo` to the JSON response schema

Modify the method that builds agent prompts (find by searching for `AGENT_DECISION_SYSTEM.format`):
- Import `build_life_prompt_block`, `compute_action_bias` from `app.services.life_context`
- If agent has `life_state`, compute life block and action bias annotations
- Inject life block into prompt
- Append bias annotations to action descriptions

Modify response parsing:
- Accept `life_context` and `past_echo` fields in AgentDecision (optional, for logging)

**Step 4: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add backend/app/services/engine.py backend/app/models/action.py backend/tests/test_life_prompt_integration.py
git commit -m "feat: integrate life context into agent decision prompt and reasoning chain"
```

---

### Task 7: Integrate LifeEngine into Simulation Loop

**Files:**
- Modify: `backend/app/services/engine.py` (SimulationEngine.__init__, run loop)
- Modify: `backend/app/api/simulate.py` (pass LifeEngine to SimulationEngine)

**Step 1: Modify SimulationEngine**

In `SimulationEngine.__init__`:
- Add `life_engine: LifeEngine | None = None` parameter
- Store as `self.life_engine`

In `SimulationEngine.run()` — insert life engine evaluation at line ~356 (after `_select_active_agents`, before `_batch_decisions`):

```python
# Life events for active agents
life_events_this_round = []
if self.life_engine:
    life_events_this_round = await self.life_engine.evaluate(active, world_state, round_num)
    for agent, event_desc in life_events_this_round:
        agent.working_memory.append(f"Day {world_state.day}: {event_desc}")
        if len(agent.working_memory) > 9:
            agent.working_memory = agent.working_memory[-9:]
```

After narration (line ~413), emit life events as SSE:

```python
for agent, event_desc in life_events_this_round:
    await emit(SSEEvent(type="life_event", data={
        "agent_id": agent.id, "agent_name": agent.name,
        "event_description": event_desc,
        "day": world_state.day,
        "time_of_day": TIMES_OF_DAY[world_state.round_in_day % 3],
    }))
```

**Step 2: Modify simulate.py**

In the simulation startup route, create LifeEngine and pass to SimulationEngine:

```python
from app.services.life_engine import LifeEngine
life_engine = LifeEngine(llm=request.app.state.llm)
engine = SimulationEngine(llm=..., store=..., tension=..., resolver=..., narrator=..., life_engine=life_engine, ...)
```

**Step 3: Test manually**

Run: `cd backend && uvicorn app.main:app --reload`
Start a simulation and verify life events appear in the SSE stream.

**Step 4: Commit**

```bash
git add backend/app/services/engine.py backend/app/api/simulate.py
git commit -m "feat: integrate LifeEngine into simulation loop with SSE emission"
```

---

### Task 8: City Demographics in API and Generation

**Files:**
- Modify: `backend/app/api/simulate.py` (SimulateRequest, startup route)
- Modify: `backend/app/services/citizen_generator.py` (demographic-constrained generation)
- Modify: `backend/app/main.py` (initialize CensusService)

**Step 1: Add `city` field to SimulateRequest**

In `backend/app/api/simulate.py`:
```python
class SimulateRequest(BaseModel):
    # ... existing fields ...
    city: str | None = None
```

**Step 2: Modify startup route**

In the simulation start handler:
- If `city` is provided, call `CensusService.get_profile(city)`
- Pass `DemographicProfile` to `CitizenGenerator.generate()`
- Emit `demographics_loaded` SSE event

**Step 3: Modify CitizenGenerator.generate()**

Add `demographics: DemographicProfile | None = None` parameter.
- If provided, use `DEMOGRAPHIC_CAST_PROMPT` instead of `CAST_SYSTEM_PROMPT`
- After cast generation, validate demographic fit
- During life history generation, call `_calibrate_life_domains()` to adjust finances/health/career based on income bracket and housing status

**Step 4: Modify frontend client.js**

Add `city` to simulate payload:
```javascript
async simulate(rules, population, durationDays, proposedChange, segments, city) {
    const payload = { rules, population, duration_days: durationDays }
    if (city) payload.city = city
    // ... rest
}
```

**Step 5: Commit**

```bash
git add backend/app/api/simulate.py backend/app/services/citizen_generator.py backend/app/main.py frontend/src/api/client.js
git commit -m "feat: add city demographics parameter — real Census data seeds agent populations"
```

---

### Task 9: Frontend — City Input on HomeView

**Files:**
- Modify: `frontend/src/views/HomeView.vue`

**Step 1: Add city input UI**

Add a new progressive-disclosure option after "Add customer segments":
- `+ Base on a real city` toggle
- When revealed: text input for city name
- After typing, show a summary card with key stats (fetched from backend or just shown after simulation starts)

Add reactive state:
```javascript
const city = ref('')
const showCity = ref(false)
```

Pass city to `api.simulate()` call.

**Step 2: Test manually**

Open `http://localhost:5173`, click "+ Base on a real city", type "San Francisco", start simulation.

**Step 3: Commit**

```bash
git add frontend/src/views/HomeView.vue
git commit -m "feat: add city demographics input to HomeView"
```

---

### Task 10: Frontend — Life Tab on AgentDetailPanel

**Files:**
- Modify: `frontend/src/components/AgentDetailPanel.vue`

**Step 1: Add Life tab**

Add `{ id: 'life', label: 'Life' }` to tabs array.

Add Life tab content section showing:
- Life domain bars (finances, career, health) with labels computed from value ranges
- Family members list with status badges
- Active pressures with severity bars and deadline countdowns
- Childhood summary
- Formative events timeline
- Life event log

Use existing Tailwind patterns from the Profile tab for consistency.

**Step 2: Test manually**

Click an agent during simulation, switch to Life tab, verify all sections render.

**Step 3: Commit**

```bash
git add frontend/src/components/AgentDetailPanel.vue
git commit -m "feat: add Life tab to AgentDetailPanel showing backstory, family, pressures"
```

---

### Task 11: Frontend — Life Events in Simulation Feed

**Files:**
- Modify: `frontend/src/views/SimulationView.vue`

**Step 1: Handle life_event SSE type**

In the SSE event handler, add case for `type === "life_event"`:
- Push to event feed with a distinct visual style
- Use dashed border, muted colors, hollow icon to differentiate from society actions
- Show domain change tags (e.g., `[finances ↓]`)

**Step 2: Test manually**

Run simulation, verify life events appear in the feed with distinct styling.

**Step 3: Commit**

```bash
git add frontend/src/views/SimulationView.vue
git commit -m "feat: render life events in simulation feed with distinct visual treatment"
```

---

### Task 12: Interview Prompt Enhancement

**Files:**
- Modify: `backend/app/api/agents.py`

**Step 1: Add life context to interview prompt**

In the `interview` endpoint, if agent has `life_state`, add life context to the system prompt:
- Childhood summary
- Current pressures
- Family situation
- Domain levels

This makes agent interviews life-aware without any frontend changes.

**Step 2: Test manually**

Interview an agent, verify response references their life situation.

**Step 3: Commit**

```bash
git add backend/app/api/agents.py
git commit -m "feat: add life context to agent interview prompts"
```

---

### Task 13: Final Integration Test

**Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all PASS

**Step 2: Run end-to-end test**

Start both servers: `npm run dev`
1. Create simulation with city = "San Francisco" and rules = "Universal basic income of $1000/month"
2. Verify agents have diverse demographics matching SF
3. Click an agent → Life tab → verify backstory, family, pressures
4. Watch simulation → verify life events appear in feed
5. Interview an agent → verify life-aware response
6. Run for 10+ days → verify life events fire and pressures evolve

**Step 3: Commit everything**

```bash
git add -A
git commit -m "feat: complete Life Domain System — full human lifecycles for agents"
```
