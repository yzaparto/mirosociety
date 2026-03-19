# MiroSociety Life Domain System — Design Document

> Agents don't just have personalities. They have lives — childhoods that haunt them, rent that's overdue, sick parents, kids who need shoes, careers that are stagnating. Every decision is made through the weight of a whole life.

## Overview

MiroSociety agents currently have personality traits, memories, beliefs, relationships, and emotional states. They reason through FEEL → WANT → FEAR → DECIDE. This is good for producing interesting *social* behavior, but it misses the invisible forces that shape every real human decision: financial pressure, family obligation, health, career trajectory, and the formative experiences that made a person who they are.

This design adds a **Life Domain System** — a structured layer of life context that gives every agent a full backstory, ongoing life pressures, and a life events engine that changes their circumstances during the simulation. Combined with **real city demographics** from the US Census Bureau, this turns MiroSociety from "imagine a society" into "simulate how the people of San Francisco would actually react."

### What Changes

| Before | After |
|--------|-------|
| Agents have a 2-3 sentence background | Agents have a full life history: childhood, formative events, family, financial situation |
| Background is narrative-only | Formative events carry `trait_modifier` that mechanically shift personality values |
| No family model | Agents have named family members as contextual pressures (not separate agents) |
| Life is static during simulation | Life Events Engine injects personal changes: illness, job loss, promotions, family crises |
| Fictional demographics | Real census data seeds agent populations based on actual US cities |
| Decision prompt has no life context | New LIFE and HISTORY sections in the prompt; action bias annotations based on life state |
| FEEL → WANT → FEAR → DECIDE | FEEL → LIFE → PAST → WANT → FEAR → DECIDE |

### What Stays the Same

- Core personality model (honesty, ambition, empathy, confrontational, conformity)
- Three-tier memory (core + working + reflective)
- TensionEngine (world-level disruption)
- ActionResolver and all existing actions
- Reactive micro-rounds producing dialogue
- Report pipeline and fork system

---

## 1. The LifeState Model

### Data Structures

```python
class FamilyMember(BaseModel):
    name: str
    relation: str                    # "spouse", "child", "parent", "sibling"
    age: int
    status: str                      # "healthy", "ill", "estranged", "deceased"
    dependency: float                # 0.0 = independent, 1.0 = fully dependent
    bond_strength: float = 0.7       # how close they are emotionally

class FormativeEvent(BaseModel):
    age_at_event: int
    description: str                 # scene, not summary
    lasting_effect: str              # specific behavioral pattern
    trait_modifier: dict[str, float] # {"conformity": -0.1, "empathy": +0.15}

class LifePressure(BaseModel):
    domain: str                      # "finances", "health", "career", "family"
    description: str                 # specific, personal, 2 sentences
    severity: float                  # 0.0 = mild annoyance, 1.0 = crisis
    deadline_day: int | None = None  # sim day by which this must resolve
    created_day: int = 0

class LifeState(BaseModel):
    childhood_summary: str                        # 4-5 sentences, explains WHY they are who they are
    formative_events: list[FormativeEvent]         # 4-6 key life moments with trait modifiers
    family: list[FamilyMember]                     # named family members as contextual pressures

    finances: float = 0.5                          # 0.0 = crisis, 1.0 = thriving
    career: float = 0.5
    health: float = 0.5

    pressures: list[LifePressure] = []             # max ~3-4 active at a time
    life_log: list[str] = []                       # last 5 significant life events
```

### Design Rationale

**Three life domains, not five.** `finances`, `career`, `health` are the three axes that can't be derived from existing agent state. Social standing is already captured by `relationships` + `social_connections` + `faction`. Family wellbeing is derived at prompt-build time from `family[].status` and `family[].dependency`.

**No Maslow needs hierarchy stored.** Need-priority is computed at decision time from life domains and injected as a single framing sentence. This avoids double-bookkeeping and is always consistent.

**FormativeEvent carries trait_modifier.** Each backstory event mechanically shifts personality values during generation. "Grew up in poverty" → `{"price_sensitivity": +0.15, "ambition": +0.1}`. The backstory literally shapes who the agent is numerically, not just narratively.

**LifePressure has a lifecycle.** Pressures appear, escalate (deadline missed → severity increases), resolve (domain improved → pressure removed), and expire (old low-severity pressures decay). Capped at ~3-4 to keep prompts tight.

**deadline_day creates urgency.** A pressure at severity 0.6 with a deadline in 2 days produces fundamentally different behavior than severity 0.6 with no deadline.

---

## 2. The Life Events Engine

A new service that runs alongside TensionEngine. While TensionEngine disrupts the *world*, LifeEngine disrupts *individual lives*.

### Principles

1. **Probabilistic, not random.** A financially struggling agent is more likely to face eviction. A high-ambition agent is more likely to get a promotion. Events emerge from current state.
2. **Events cascade.** Job loss → financial pressure → can't afford medicine for sick parent. Problems compound like real life.
3. **Most rounds are uneventful.** Only 1-2 agents per evaluation cycle get a life event. Quiet stability is realistic.
4. **Good things happen too.** ~35% of events are positive. Promotions, windfalls, recoveries, family milestones.

### Event Catalog

A weighted catalog of event templates organized by domain. Each template specifies:
- `domain_delta`: how much the life domain changes
- `pressure`: what new pressure is created (if any)
- `weight_factors`: what makes this event more/less likely for a given agent

Weight factor types:
- `"inverse"`: probability increases as domain value decreases (poor health → more likely to get sick)
- `"direct"`: probability increases as trait/domain value increases (high ambition → more likely to get promoted)
- `"required"`: event can only fire if condition is true (family events require having family)

**Domains covered:** finances (unexpected expenses, windfalls, debt), career (job threats, promotions, public failures), health (illness, injury, recovery), family (family illness, conflict, milestones, dependent needs).

### Engine Cycle

```
EVAL_INTERVAL = 6 rounds (every 2 sim-days)
MAX_EVENTS_PER_CYCLE = 2
MAX_PRESSURES_PER_AGENT = 4
POSITIVE_RATIO = 0.35
```

Each cycle:
1. **Tick pressures** — escalate overdue, resolve improved, decay old
2. **Select candidates** — agents most "due" for a life event (weighted by time since last event, domain extremes, personality)
3. **Fire events** — select from catalog based on weight factors, personalize via LLM
4. **Apply cascades** — check cascade rules for follow-on effects

### Pressure Lifecycle

- **Deadline passed:** severity increases by 0.2, deadline cleared (now chronic)
- **Domain improved above 0.7 + severity below 0.4:** pressure resolved, logged
- **Age > 20 days + severity below 0.3:** pressure decays naturally

### Cascade Rules

Event chains defined as condition → effect mappings:
- `job_threat` + `finances < 0.4` → financial pressure (savings running out)
- `family_illness` + high-dependency family → financial pressure (medical costs)
- `family_illness` + `empathy > 0.6` → health delta -0.1 (stress of caregiving)
- `unexpected_expense` + `finances < 0.3` → career pressure (desperate for income)

### Integration Point

LifeEngine evaluates **between agent selection and decision** (so life events influence the same round's decision) and **after tension check** at cycle intervals for inactive agents.

### Event Personalization

One LLM call (~100 tokens output) per event, turning template into specific narrative:
- "A major unexpected expense hits" → "The roof of Marcus's house collapsed during the storm — with winter coming and two children under 10, he needs 40 units of goods to repair it before the first frost."

---

## 3. Decision Prompt Integration

### New Prompt Sections

Two new sections added to the agent decision prompt:

**YOUR LIFE RIGHT NOW** — computed need-priority + active pressures + family summary + domain levels as human-readable text (not raw floats).

**YOUR HISTORY** — childhood summary + contextually relevant formative event echoes.

### Domain Level Translation

Raw floats are never shown to the LLM. They're translated to narrative:

| Range | Level | Example (finances) |
|-------|-------|-------------------|
| 0.0-0.2 | desperate | "you can barely feed yourself, let alone your family" |
| 0.2-0.35 | struggling | "every trade matters — you're one bad week from crisis" |
| 0.35-0.5 | tight but managing | "you get by, but there's no safety margin" |
| 0.5-0.65 | stable | "you're not rich, but money isn't keeping you up at night" |
| 0.65-0.8 | comfortable | "you can afford to take a risk here and there" |
| 0.8-1.0 | thriving | "money is the last thing on your mind" |

Similar flavor tables for career and health.

### Modified Reasoning Chain

```
1. FEEL: What is your emotional reaction to the current situation?
2. LIFE: How does your current life situation (family, money, health, pressures) affect how you see this?
3. PAST: Does anything in your history make you react differently than most people would?
4. WANT: Given ALL of the above, what do you want right now?
5. FEAR: What could go wrong — for you AND for the people who depend on you?
6. DECIDE: What action do you take?
```

Two new JSON response fields: `life_context` and `past_echo`. These force the LLM to reason through life context before choosing an action, making backstory causal rather than decorative.

### Mechanical Action Biasing

Actions get contextual annotations based on life state. The action space stays full (no actions removed) but annotations shift emotional weight:

- **Financial desperation:** TRADE gets "(you NEED resources — this is urgent)"; DEFECT gets "(risky — if caught, your family suffers)" when dependents exist
- **Health crisis:** BUILD gets "(you don't have the physical energy)"; OBSERVE gets "(rest and watching is all you can manage)"
- **High dependency:** DEFECT and PROTEST get "(think about your family)"; SPEAK_PRIVATE gets "(ask for help — your family is counting on you)"
- **Career pressure:** COMPLY gets "(you need to be seen as reliable right now)"; BUILD gets "(proving yourself could save your position)"
- **Imminent deadline:** DO_NOTHING gets "(you can't afford to wait — {pressure_description})"
- **Thriving:** PROPOSE_RULE gets "(you have the standing to shape the rules)"; BUILD gets "(you can afford to invest)"

Annotations are nudges, not restrictions. An agent *can* still PROTEST with kids at home — and those are the most interesting moments.

### Contextual Echo Matching

Formative events aren't listed every round. They're pattern-matched against the current situation and surfaced only when relevant:
- Authority situations (rules, leaders) → echo authority-related formative events
- Scarcity situations → echo poverty/loss experiences
- Trust situations → echo betrayal/abandonment experiences
- Belonging situations → echo isolation/rejection experiences

Max 2 echoes per round to keep prompts tight.

### Token Budget

| Section | Tokens |
|---------|--------|
| Childhood summary | ~90 |
| Formative events (4-6 × 30) | ~150 |
| Family summary | ~25 |
| Need priority | ~20 |
| Active pressures (2-3 × 40) | ~100 |
| Relevant echoes (0-2) | ~50 |
| Domain levels with flavor | ~40 |
| Action bias annotations | ~15 |
| **Total input addition** | **~490** |
| `life_context` + `past_echo` output | ~60 |

At 25 agents, 3 rounds/day: ~37K extra input tokens/day, ~4.5K output tokens/day. At gpt-4o-mini pricing: ~$0.008/day.

---

## 4. Backstory Generator with Real City Demographics

### Census Data Integration

Two free public APIs provide real demographic data for any US city:

**Census Bureau ACS (American Community Survey)**
- Endpoint: `https://api.census.gov/data/2023/acs/acs5/profile`
- Free API key (optional for <500 queries/day)
- Four profile tables: DP02 (social), DP03 (economic), DP04 (housing), DP05 (demographic)
- Available at city/place level via FIPS codes

**Bureau of Labor Statistics OEWS**
- Endpoint: `https://api.bls.gov/publicAPI/v2/timeseries/data/`
- No key required for basic access
- Occupation breakdown by metropolitan area (800+ SOC categories)

### DemographicProfile Model

```python
class DemographicProfile(BaseModel):
    city_name: str
    state: str
    population: int
    age: list[AgeDistribution]           # brackets: 18-24, 25-34, 35-44, 45-54, 55-64, 65+
    income: list[IncomeDistribution]     # brackets: <25K, 25-50K, 50-75K, 75-100K, 100-150K, 150K+
    occupations: list[OccupationDistribution]
    ethnicity: list[EthnicityDistribution]
    median_household_income: int
    poverty_rate: float
    unemployment_rate: float
    homeownership_rate: float
    median_rent: int
    rent_burden_rate: float              # % of renters spending >30% income on rent
    college_education_rate: float
    median_age: float
    city_character: str                  # LLM-generated qualitative summary
```

### CensusService

- Pre-populated FIPS lookup table for top ~100 US cities
- Parallel fetch of DP02, DP03, DP05 tables
- Results cached to SQLite with 30-day TTL
- **Graceful fallback:** if city not in FIPS table or API fails, LLM estimates demographics from world knowledge

### Demographic-Constrained Cast Generation

When a city is selected, the cast generation prompt receives real demographic data and strict instructions:
- Age distribution must match census proportions
- Income distribution must reflect real inequality
- Occupations proportional to city's industry breakdown
- Names and cultural backgrounds reflect ethnic composition
- Housing situations calibrated to homeownership rate and rent burden
- Poverty rate determines minimum number of financially struggling agents

Post-generation validation checks cast against demographic targets with 15% tolerance and logs deviations.

### Life Domain Calibration

Income bracket + housing status → base `finances` value, adjusted by rent burden. City-specific pressures auto-generated (e.g., rent-burdened agent in SF's Mission district gets an initial financial pressure).

### Non-US Cities

Falls back to LLM demographic estimation. The LLM is asked to estimate age distribution, income levels, ethnic composition, occupation categories, poverty rate, housing affordability. Not Census-accurate, but sufficient for representative cast generation.

---

## 5. Frontend Changes

### HomeView — City Input

New progressive-disclosure option: "+ Base on a real city". Reveals a city input with live search. When a city is resolved, shows a summary card:

```
San Francisco, CA
Pop: 870K · Median income: $120K · Poverty: 11% · Rent-burdened: 46%
✓ Real census data (ACS 2023)
```

City name sent as new `city` field in `/api/simulate` payload.

### AgentDetailPanel — Life Tab

Fourth tab added: **Life**. Shows:
- Life domain bars (finances, career, health) with human-readable labels
- Family members with status and dependency
- Active pressures with severity bars and deadlines
- Childhood summary and formative events
- Life event log

### Simulation Feed — Life Events

Life events appear in the timeline with distinct visual treatment (dashed borders, hollow icon) and small domain-change tags: `[finances ↓ 0.1]`.

### Generation Phase

Extra progress line when city demographics are loaded: "Demographics loaded: SF census data".

### New SSE Events

- `life_event`: agent_id, description, domain_changes, new_pressures, day, time_of_day
- `demographics_loaded`: city, state, source (census_acs_2023 | llm_estimate), key stats, summary

---

## 6. Generation Pipeline Changes

### Updated Flow

```
1. Generate cast (existing, enhanced with demographic constraints)
2. Generate personas (existing)
3. Generate life histories (NEW — one LLM call per agent, batched in 5s, max_tokens=1200)
4. Apply trait modifiers from formative events (NEW — pure computation, no LLM)
5. Enforce life diversity (NEW — audit distributions, correct LLM drama bias)
6. Generate relationships (existing, now informed by family/neighborhood context)
7. Assign knowledge levels (existing, market only)
```

### Trait Modifier Application

Formative event trait modifiers stack with damping: 1st event = 100% effect, 2nd = 67%, 3rd = 50%. Prevents runaway personality values from multiple events hitting the same trait.

### Life Diversity Enforcement

Post-generation audit corrects LLM bias toward dramatic backstories:
- If average finances < 0.35, push top quartile toward stability (0.6-0.85)
- If average health < 0.4, push top third toward healthy (0.7-0.95)
- Ensure at least 20% of agents have zero active pressures
- Ensure at least ~15% of agents have minimal family (some people are alone)

---

## 7. API Changes

### POST /api/simulate — New Fields

```json
{
  "rules": "...",
  "population": 25,
  "duration_days": 30,
  "proposed_change": null,
  "segments": null,
  "city": "San Francisco, CA"
}
```

`city` is optional. When provided, triggers demographic fetch and constrained generation.

### GET /api/simulation/{id}/agent/{aid} — Extended Response

Agent response now includes `life_state` object with all life domains, family, pressures, backstory, and life log.

### GET /api/simulation/{id}/demographics — New Endpoint

Returns the DemographicProfile used to seed the simulation (if city-based).

---

## 8. Cost Analysis

### Generation (One-Time)

| Step | Calls | Input tokens/call | Output tokens/call | Total |
|------|-------|-------------------|-------------------|-------|
| Life history generation | 25 (batched 5×5) | ~600 | ~1000 | ~40K tokens |
| Event personalization | 0 at generation | — | — | 0 |
| **Total generation overhead** | | | | **~40K tokens (~$0.006 at gpt-4o-mini)** |

### Per Simulation Day (25 agents, 3 rounds)

| Component | Extra tokens/day | Cost/day (gpt-4o-mini) |
|-----------|-----------------|----------------------|
| Life context in decision prompts | ~37K input | ~$0.006 |
| life_context + past_echo output | ~4.5K output | ~$0.002 |
| Life event personalization (~0.3 events/day avg) | ~200 | negligible |
| **Total daily overhead** | **~42K tokens** | **~$0.008** |

### Full Simulation (100 days)

~$0.80 additional at gpt-4o-mini. ~$12 at gpt-4o. Negligible relative to existing simulation cost.
