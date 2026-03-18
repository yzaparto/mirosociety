# MiroSociety — Implementation Plan

> **For Claude / Cursor:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-agent society simulation engine where users define social rules and watch emergent behavior unfold.

**Architecture:** FastAPI backend with custom simulation engine (tension engine, reactive micro-rounds, tiered memory), Vue 3 + D3.js frontend with progressive streaming, SQLite state storage, OpenAI-compatible LLM for agent reasoning and narration.

**Tech Stack:** Python 3.11+ (FastAPI, Pydantic, aiosqlite, openai), Vue 3 (Composition API, Vite, D3.js, TailwindCSS), Docker

---

## Task 1: Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.js`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `.gitignore`

**Step 1: Create backend scaffold**

`backend/pyproject.toml`:
```toml
[project]
name = "mirosociety"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "openai>=1.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "aiosqlite>=0.20.0",
    "python-dotenv>=1.0.0",
    "sse-starlette>=2.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    database_dir: str = "data"
    host: str = "0.0.0.0"
    port: int = 8000
    max_concurrent_llm_calls: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MiroSociety", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 2: Create frontend scaffold**

Standard Vue 3 + Vite + TailwindCSS setup with vue-router. Single `App.vue` with `<router-view>`. Routes: `/` (home), `/simulation/:id` (sim view — handles both generation and running), `/report/:id` (report), `/gallery` (community gallery).

**Step 3: Create Docker and env files**

`docker-compose.yml` with single service (port 8000). Multi-stage Dockerfile.

`.env.example`:
```
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**Step 4: Init git repo**

```bash
cd /Users/yashgupta/Desktop/opensource/mirosociety
git init
git add .
git commit -m "feat: initial project scaffold"
```

---

## Task 2: Data Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/world.py`
- Create: `backend/app/models/agent.py`
- Create: `backend/app/models/action.py`
- Create: `backend/app/models/simulation.py`

**Step 1: Define world models**

`backend/app/models/world.py` — Pydantic models:
- `Location(id, name, type: Literal["public", "commerce", "governance", "residential", "social"], description)`
- `TimeConfig(total_days, rounds_per_day: int = 3, active_agents_per_round_min, active_agents_per_round_max)`
- `WorldBlueprint(name, description, rules: list[str], locations: list[Location], resources: list[str], initial_tensions: list[str], time_config: TimeConfig)`
- `WorldMetrics(stability: float, prosperity: float, trust: float, freedom: float, conflict: float)` — all 0.0-1.0
- `Institution(name, purpose, founder_id, member_ids: list[int], rules: list[str], created_day: int)`
- `Proposal(id, proposer_id, content, votes_for: list[int], votes_against: list[int], status: Literal["open", "passed", "rejected"], created_round: int)`
- `WorldState(blueprint, metrics, institutions: list[Institution], proposals: list[Proposal], day, round_in_day, active_disputes: list[str], community_rules: list[str])`

**Step 2: Define agent models with tiered memory**

`backend/app/models/agent.py` — Pydantic models:
- `Personality(honesty, ambition, empathy, confrontational, conformity)` — all floats 0-1
- `AgentPersona(id, name, role, age, personality: Personality, background, goals: list[str], core_memory: list[str], working_memory: list[str], beliefs: list[str], relationships: dict[str, str], resources: dict[str, int], location, faction: str | None, emotional_state: str)`

Note: `relationships` is `dict[str, str]` where key = agent_id as string, value = description of relationship. Using string keys for JSON compatibility.

**Step 3: Define action models with internal thought**

`backend/app/models/action.py`:
- `ActionType(Enum)`: SPEAK_PUBLIC, SPEAK_PRIVATE, TRADE, FORM_GROUP, PROPOSE_RULE, VOTE, PROTEST, COMPLY, DEFECT, BUILD, MOVE, OBSERVE, DO_NOTHING
- `AgentDecision(feel, want, fear, action: ActionType, args: dict, speech: str | None, internal_thought: str, belief_updates: list[str], memory_promotion: str | None)`
- `ActionEntry(round, day, time_of_day, agent_id, agent_name, location, action_type: ActionType, action_args: dict, speech: str | None, internal_thought: str | None, targets: list[int], world_state_changes: dict, relationship_changes: dict)`
- `ReactiveResponse(agent_id, reaction_type: Literal["respond", "whisper", "silent"], content: str | None, target_id: int | None)`

**Step 4: Define simulation models**

`backend/app/models/simulation.py`:
- `SimulationStatus(Enum)`: GENERATING_WORLD, GENERATING_CITIZENS, RUNNING, PAUSED, COMPLETED, ERROR
- `SpeedMode(Enum)`: LIVE, FAST_FORWARD, JUMP
- `SimulationState(id, status, speed_mode, world_blueprint: WorldBlueprint | None, agents_generated: int, agents_total: int, current_day, current_round, total_rounds, action_count, created_at)`
- `SSEEvent(type: Literal["world_ready", "citizen_generated", "round_complete", "narrative", "metrics_update", "injection_result", "simulation_complete", "error"], data: dict)`
- `ForkRequest(source_simulation_id, fork_at_day, changes: str)`

**Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add core data models with tiered memory and reactive actions"
```

---

## Task 3: Database Layer

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/store.py`

**Step 1: Build async SQLite store**

Each simulation gets its own directory: `data/simulations/{sim_id}/`
- `simulation.db` — all tables for this simulation
- `actions.jsonl` — append-only action log (for fast streaming reads)

Tables in `simulation.db`:
- `meta(key TEXT PRIMARY KEY, value JSON)` — simulation config, status, blueprint
- `agents(agent_id INT PRIMARY KEY, state JSON, updated_at TEXT)`
- `world_state(round INT PRIMARY KEY, state JSON)`
- `actions(id INTEGER PRIMARY KEY AUTOINCREMENT, round INT, day INT, entry JSON)`
- `narratives(round INT PRIMARY KEY, day INT, time_of_day TEXT, text TEXT)`
- `metrics_history(round INT PRIMARY KEY, metrics JSON)`

Global database `data/global.db`:
- `simulations(id TEXT PRIMARY KEY, status TEXT, rules_text TEXT, world_name TEXT, agent_count INT, created_at TEXT, is_public BOOL, view_count INT, fork_count INT, forked_from TEXT)`

Methods:
```python
class SimulationStore:
    async def create(sim_id, rules_text) -> None
    async def get_meta(sim_id) -> dict
    async def set_meta(sim_id, key, value) -> None
    async def save_agent(sim_id, agent: AgentPersona) -> None
    async def save_agents_batch(sim_id, agents: list[AgentPersona]) -> None
    async def get_agent(sim_id, agent_id) -> AgentPersona
    async def get_all_agents(sim_id) -> list[AgentPersona]
    async def save_world_state(sim_id, round_num, state: WorldState) -> None
    async def get_world_state(sim_id, round_num: int | None = None) -> WorldState
    async def save_action(sim_id, entry: ActionEntry) -> None
    async def save_narrative(sim_id, round_num, day, time_of_day, text) -> None
    async def save_metrics(sim_id, round_num, metrics: WorldMetrics) -> None
    async def get_actions(sim_id, from_round, to_round) -> list[ActionEntry]
    async def get_narratives(sim_id, from_day, to_day) -> list[dict]
    async def get_metrics_history(sim_id) -> list[dict]
    async def list_simulations(public_only=False) -> list[dict]
    async def copy_state_at_round(source_sim_id, target_sim_id, round_num) -> None
```

**Step 2: Commit**

```bash
git add backend/app/db/
git commit -m "feat: add async SQLite storage with per-simulation databases"
```

---

## Task 4: LLM Client

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/llm.py`

**Step 1: Build LLM client wrapper**

```python
class LLMClient:
    def __init__(self, api_key, base_url, model, max_concurrent):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.total_tokens = 0
        self.total_calls = 0

    async def generate(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 1000) -> str:
        """Single LLM call with semaphore, retries (3x exponential backoff), JSON mode."""

    async def generate_batch(self, prompts: list[tuple[str, str]], json_mode: bool = False, max_tokens: int = 1000) -> list[str]:
        """Concurrent LLM calls via asyncio.gather, respecting semaphore."""

    async def generate_light(self, system: str, user: str, max_tokens: int = 100) -> str:
        """Lightweight call for reactive micro-rounds. Low max_tokens, no JSON mode."""

    def get_stats(self) -> dict:
        """Return total_tokens, total_calls, estimated_cost."""
```

JSON parsing: try `json.loads()`, if fails try to extract JSON from markdown fences, if fails try to repair truncated JSON (close open braces/brackets), if still fails log error and return a safe default.

**Step 2: Commit**

```bash
git add backend/app/services/llm.py
git commit -m "feat: add async LLM client with batching and lightweight mode"
```

---

## Task 5: World Generator

**Files:**
- Create: `backend/app/services/world_generator.py`

**Step 1: Build world generator**

```python
class WorldGenerator:
    def __init__(self, llm: LLMClient): ...

    async def generate(self, rules_text: str, population: int = 25, duration_days: int = 365) -> WorldBlueprint:
```

System prompt:
```
You are a world-builder for a society simulation engine.

Given the user's rules for a society, design a small town that will be
interesting to simulate. Your job is to create CONFLICT POTENTIAL —
the world should have built-in tensions that make the rules interact
with human nature in surprising ways.

Generate a JSON world blueprint with:
- name: A evocative name for this society (2-3 words max)
- description: One sentence capturing the essence
- rules: The user's rules as a clean list (clarify ambiguities, add
  implied consequences)
- locations: 5-8 locations. Mix of:
  - 1-2 public gathering spaces
  - 1-2 commerce/trade locations
  - 1 governance/authority location
  - 1-2 residential/private spaces
  - 1 social/leisure space
  Each location should create different social dynamics.
- resources: 4-6 resource types that matter in this society. Always
  include "influence" and "knowledge". Others depend on the rules.
- initial_tensions: 2-4 inherent conflicts created by the rules.
  Think: who benefits from these rules? Who suffers? What loopholes exist?
  What happens when the rules conflict with basic human needs?
- time_config: { total_days: {duration}, rounds_per_day: 3,
  active_agents_per_round_min: 3, active_agents_per_round_max: {population * 0.4} }
```

**Step 2: Commit**

```bash
git add backend/app/services/world_generator.py
git commit -m "feat: add world generator with conflict-oriented prompting"
```

---

## Task 6: Citizen Generator

**Files:**
- Create: `backend/app/services/citizen_generator.py`

**Step 1: Build citizen generator (streaming)**

```python
class CitizenGenerator:
    def __init__(self, llm: LLMClient): ...

    async def generate(self, blueprint: WorldBlueprint, count: int = 25,
                       on_citizen: Callable = None) -> list[AgentPersona]:
        """
        Generates citizens in two phases, streaming each one via on_citizen callback.

        Phase 1: Cast sheet (single LLM call)
        Generate a list of count citizens with: name, role, age, one-line personality
        hook, stance on each initial_tension (for/against/indifferent/exploiter).
        Ensure diversity: age range 18-75, mix of genders, roles that cover
        all locations, personality spread, at least 2 citizens per tension stance.

        Phase 2: Full personas (batched, 5 at a time)
        For each citizen, generate full persona. As each completes, call
        on_citizen(agent) to stream to frontend.
        """

    async def generate_relationships(self, blueprint: WorldBlueprint,
                                     agents: list[AgentPersona]) -> list[AgentPersona]:
        """
        Single LLM call: given all citizen summaries, generate initial
        relationship graph. Output: list of {agent_id, relationships: {target_id: description}}.
        Ensure: at least 2 relationships per citizen, mix of positive/negative/neutral,
        some family ties, some professional ties, some rivalries.
        """
```

Key prompt constraint for persona generation:
```
CRITICAL: Citizens must have DIVERSE stances on the society's rules.
For each initial tension, generate citizens across the spectrum:
- True believers who love the rules
- Pragmatists who comply but have reservations
- Quiet dissenters who obey but resent it
- Active resisters who will test boundaries
- Exploiters who find loopholes
- The indifferent who just want to be left alone

This diversity drives the simulation. A town of reasonable moderates is boring.
A town with extremists, idealists, cynics, and opportunists produces stories.
```

**Step 2: Commit**

```bash
git add backend/app/services/citizen_generator.py
git commit -m "feat: add streaming citizen generator with diversity constraints"
```

---

## Task 7: Simulation Engine (Core)

**Files:**
- Create: `backend/app/services/engine.py`
- Create: `backend/app/services/tension.py`
- Create: `backend/app/services/resolver.py`

**Step 1: Build tension engine**

`backend/app/services/tension.py`:
```python
class TensionEngine:
    def __init__(self, llm: LLMClient): ...

    async def check_and_apply(self, world_state: WorldState, agents: list[AgentPersona],
                              metrics_history: list[WorldMetrics]) -> tuple[WorldState, list[AgentPersona], str | None]:
        """
        Check if society has reached boring equilibrium:
        - stability > 0.85 and conflict < 0.15 for 3+ consecutive rounds
        - OR no significant actions (proposals, protests, defections) for 5+ rounds
        - OR dominant faction has >60% of agents

        If triggered, apply ONE of:
        1. Internal pressure: modify 2-3 agent beliefs/emotions
        2. External event: generate environmental change via LLM
        3. Faction fracture: seed splinter ideology in dominant faction

        Returns: updated world_state, updated agents, event_description (or None)
        """
```

**Step 2: Build action resolver**

`backend/app/services/resolver.py`:
```python
class ActionResolver:
    def resolve(self, decisions: list[tuple[AgentPersona, AgentDecision]],
                world_state: WorldState, all_agents: list[AgentPersona]) -> tuple[list[ActionEntry], WorldState, list[AgentPersona]]:
        """
        Process decisions in order of influence_weight:

        SPEAK_PUBLIC/PRIVATE: Always succeeds. Records speech.
        TRADE: Succeeds only if both parties have sufficient resources.
        FORM_GROUP: Creates institution or adds member. Updates faction.
        PROPOSE_RULE: Creates open Proposal in world state.
        VOTE: Adds vote to active Proposal. If quorum reached, resolve.
        PROTEST: Decreases stability, increases conflict. May trigger
                 reactive responses from authority figures.
        COMPLY: Increases stability. May decrease agent's emotional wellbeing.
        DEFECT: Roll detection check based on location privacy and nearby
                agents' observation scores. If detected, becomes public knowledge.
        BUILD: Requires resources. Creates new location or modifies existing.
        MOVE: Updates agent location.
        OBSERVE: Agent gains information about nearby agents' recent actions.
        DO_NOTHING: No effect but recorded (useful for narrator).

        Returns: resolved actions, updated world state, updated agents.
        """

    def _update_metrics(self, old_metrics: WorldMetrics, actions: list[ActionEntry],
                        world_state: WorldState) -> WorldMetrics:
        """
        Heuristic metric updates with exponential moving average (alpha=0.3):
        - stability: +0.02 per comply/vote, -0.05 per protest, -0.08 per defect
        - prosperity: +0.01 per trade, -0.02 per build (investment), track total resources
        - trust: +0.01 per positive relationship change, -0.02 per negative
        - freedom: inversely correlated with len(community_rules) and len(institutions)
        - conflict: +0.03 per protest/defect, -0.01 per comply, spikes on proposals
        All clamped to [0.0, 1.0].
        """
```

**Step 3: Build main engine**

`backend/app/services/engine.py`:
```python
class SimulationEngine:
    def __init__(self, llm: LLMClient, store: SimulationStore,
                 tension: TensionEngine, resolver: ActionResolver): ...

    async def run(self, simulation_id: str, emit: Callable[[SSEEvent], None]):
        """
        Main loop. Runs until stopped, paused, or total_rounds reached.

        For each round:
        1. Load current world state and agents
        2. tension_engine.check_and_apply() — inject pressure if equilibrium
        3. select_active_agents() — pick subset
        4. Concurrent agent_decision() calls for all active agents
        5. Reactive micro-rounds for speech acts
        6. resolver.resolve() — apply all actions
        7. Update agent memories (working_memory window, core_memory promotions)
        8. Save state, actions, metrics to store
        9. If speed_mode == LIVE or round is significant:
              narrator.narrate_round() and save narrative
        10. emit SSEEvent with round data
        11. If speed_mode == JUMP and not significant, skip to step 1

        Significance score = number of (protests + defections + proposals + faction changes
        + relationship sign-flips + rule changes) in this round. Threshold = 1 for JUMP mode.
        """

    def select_active_agents(self, world_state: WorldState,
                             agents: list[AgentPersona], round_num: int) -> list[AgentPersona]:
        """
        Base count: random between config min and max.
        Boost for:
        - Open proposals: all agents with faction or opinion get +0.3 activation chance
        - Recent conflict (last 2 rounds): nearby agents get +0.5 activation chance
        - Injected event: all agents get +0.4 activation chance for 2 rounds
        - Emotional state "restless"/"angry"/"fearful": +0.3 activation chance
        Never exceed 60% of population.
        Selection: weighted random by (base_chance + boosts + activity_personality_score).
        """

    async def agent_decision(self, agent: AgentPersona, world_state: WorldState,
                             active_agents: list[AgentPersona]) -> AgentDecision:
        """
        Build prompt per design doc (feel/want/fear scaffold).
        Available actions filtered by location:
        - VOTE only if there's an open proposal
        - TRADE only if at commerce location or near another agent
        - PROPOSE_RULE only at governance location
        - BUILD only with sufficient resources

        Parse JSON response. Validate action type and args.
        Fallback to DO_NOTHING if parse fails.
        """

    async def reactive_micro_round(self, speech_actions: list[ActionEntry],
                                    agents: list[AgentPersona],
                                    world_state: WorldState) -> list[ReactiveResponse]:
        """
        For each SPEAK_PUBLIC action, identify witnesses (agents at same location).
        For each SPEAK_PRIVATE action, only the target witnesses.
        Batch lightweight LLM calls:
            "You are {name}. You just heard {speaker} say: '{content}'
             React: (a) respond publicly (b) whisper to someone (c) stay silent.
             Reply with just the letter and an optional one-sentence response."
        Parse responses. Return list of ReactiveResponse.
        """

    async def inject_event(self, simulation_id: str, event_text: str) -> str:
        """
        LLM call: "An event occurs in {world_name}: '{event_text}'.
        Describe: 1) What physically happens 2) Which agents are directly affected
        3) Any resource/location changes. Return JSON."
        Apply changes to world state.
        Add event to all affected agents' working memory.
        Return narrative description.
        """

    async def reflective_memory_pass(self, simulation_id: str):
        """
        Called every 30 simulated days.
        For each agent, LLM call:
        "You are {name}. Here is everything significant from the past 30 days:
        {working_memory_full_history}
        Your current core memories: {core_memory}
        Your current beliefs: {beliefs}
        Update: 1) core_memory (max 10 items) 2) beliefs 3) goals.
        Drop anything no longer relevant. Add anything now important."
        """

    # Pause/resume via asyncio.Event flag
    _pause_event: asyncio.Event

    async def pause(self, simulation_id): ...
    async def resume(self, simulation_id): ...
    async def set_speed(self, simulation_id, mode: SpeedMode): ...
```

**Step 4: Commit**

```bash
git add backend/app/services/engine.py backend/app/services/tension.py backend/app/services/resolver.py
git commit -m "feat: add simulation engine with tension engine and reactive micro-rounds"
```

---

## Task 8: Narrator Service

**Files:**
- Create: `backend/app/services/narrator.py`

**Step 1: Build narrator with continuity**

```python
class Narrator:
    def __init__(self, llm: LLMClient): ...

    async def narrate_round(self, world_state: WorldState,
                            actions: list[ActionEntry],
                            reactions: list[ReactiveResponse],
                            previous_narrative: str | None,
                            tension_event: str | None) -> str:
        """
        Prompt:
        "You are narrating events in {world_name}. Rules: {rules}.

        Previous scene (for continuity): {previous_narrative}

        Actions this round: {actions with speech, internal thoughts, reactions}
        {tension_event if any}

        Write 2-4 paragraphs as if writing a literary novel.
        - Use character names and dialogue (with quotation marks)
        - Show body language and emotion
        - When you know a character's internal thought, show it in italics
          as indirect narration (e.g. 'Elena nodded, though privately she
          doubted Marcus had the stomach for what was coming.')
        - If a tension event occurred, weave it in naturally
        - End with something unresolved — a glance, a question, a tension
        - Do NOT explain rules or editorialize. Just tell the story."
        """

    async def summarize_epoch(self, narratives: list[str], metrics_start: WorldMetrics,
                              metrics_end: WorldMetrics, day_start: int, day_end: int) -> str:
        """Compress 30 days of narratives into a 2-3 paragraph epoch summary."""

    async def generate_report(self, simulation_id: str, store: SimulationStore) -> dict:
        """
        Multi-stage pipeline:
        Stage 1: Generate epoch summaries (1 per 30 days)
        Stage 2: Feed all epochs + metrics to LLM for trend extraction
        Stage 3: Compose final report:
          {
            "title": "...",
            "summary": "one paragraph of what happened",
            "key_moments": [{"day": N, "title": "...", "description": "..."}],
            "surprise": "the most unexpected emergent behavior",
            "factions": [{"name": "...", "description": "...", "peak_members": N}],
            "metrics_history": [...],
            "total_actions": N,
            "total_days": N,
            "agent_count": N
          }
        """
```

**Step 2: Commit**

```bash
git add backend/app/services/narrator.py
git commit -m "feat: add narrator with literary style and multi-stage report pipeline"
```

---

## Task 9: API Routes

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/simulate.py`
- Create: `backend/app/api/agents.py`
- Create: `backend/app/api/gallery.py`
- Create: `backend/app/api/presets.py`
- Create: `backend/app/presets.py`
- Modify: `backend/app/main.py` — register routers, create service instances on startup

**Step 1: Unified simulate endpoint**

```python
# POST /api/simulate
# Request: { "rules": "...", "population": 25, "duration_days": 365 }
# Response: { "simulation_id": "..." }
# Kicks off the full pipeline in background: generate world → stream citizens → start simulation

# GET /api/simulation/{id}/stream
# SSE stream. Events:
#   { "type": "status", "data": { "status": "generating_world" } }
#   { "type": "world_ready", "data": WorldBlueprint }
#   { "type": "citizen_generated", "data": AgentPersona }
#   { "type": "round_complete", "data": { "day": N, "round": N, "actions": [...], "metrics": {...} } }
#   { "type": "narrative", "data": { "day": N, "time_of_day": "morning", "text": "..." } }
#   { "type": "fast_forward_summary", "data": { "from_day": N, "to_day": N, "summary": "..." } }
#   { "type": "simulation_complete", "data": { "total_days": N, "total_actions": N } }
#   { "type": "error", "data": { "message": "..." } }

# GET /api/simulation/{id}/state
# POST /api/simulation/{id}/inject  { "event": "..." }
# POST /api/simulation/{id}/fork    { "fork_at_day": N, "changes": "..." }
# POST /api/simulation/{id}/speed   { "mode": "live" | "fast_forward" | "jump" }
# POST /api/simulation/{id}/pause
# POST /api/simulation/{id}/resume
# POST /api/simulation/{id}/stop
# GET  /api/simulation/{id}/report
```

**Step 2: Agent routes**

```python
# GET  /api/simulation/{sim_id}/agents
# GET  /api/simulation/{sim_id}/agent/{agent_id}
# POST /api/simulation/{sim_id}/agent/{agent_id}/interview
#   Request: { "question": "..." }
#   Response: { "response": "...", "emotional_state": "..." }
```

Interview prompt:
```
You are {name}, {role} in {world_name}. Current day: {day}.
Your personality: {personality}
Your core memories: {core_memory}
Your beliefs: {beliefs}
Your emotional state: {emotional_state}

Someone approaches and asks: "{question}"

Respond in character. Be authentic to your personality — if you're
guarded, be guarded. If you're passionate, be passionate. Reference
specific events from your memory. Keep it to 2-3 sentences.
```

**Step 3: Gallery routes**

```python
# POST /api/simulation/{id}/publish    — mark simulation as public
# GET  /api/gallery                    — list public sims (sort: recent, views, forks)
# GET  /api/gallery/{id}               — public sim report (read-only)
# POST /api/gallery/{id}/fork          — fork public sim with modified rules
```

**Step 4: Preset routes and data**

```python
# GET /api/presets

PRESETS = [
    {
        "id": "no-lies",
        "name": "Nobody Can Lie",
        "rules": "Lying is physically impossible. Every person can only speak what they believe to be true. Emotions are visible on everyone's face and cannot be hidden.",
        "teaser": "They invented silence clubs by month 3.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "full-communism",
        "name": "Full Communism",
        "rules": "No private property exists. All resources are communal. No one can own more than they need. A community council allocates resources based on need.",
        "teaser": "It worked. Then it didn't.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "everyone-armed",
        "name": "Everyone Is Armed",
        "rules": "Every citizen carries a weapon at all times. Violence is always a legal option for resolving disputes. There are no police — only self-defense.",
        "teaser": "Politeness became a survival skill.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "total-surveillance",
        "name": "Total Surveillance",
        "rules": "Everyone can see what everyone else is doing at all times. There are no secrets, no private spaces, no hidden actions. All conversations are public.",
        "teaser": "The most powerful person was the one who stopped watching.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "direct-democracy",
        "name": "Direct Democracy",
        "rules": "Every decision that affects more than one person must be voted on by the entire community. No representatives, no delegation. Every citizen has equal vote.",
        "teaser": "They voted 47 times on day 1. By day 30, nobody showed up.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "no-digital",
        "name": "No Phones, No Internet",
        "rules": "All communication is face-to-face only. No long-distance messaging, no written notes left behind, no technology for communication. You must be physically present to interact.",
        "teaser": "Rumors moved slower but hit harder.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "meritocracy",
        "name": "Absolute Meritocracy",
        "rules": "Social status, housing, food quality, and privileges are strictly determined by measurable productive output. Nothing else matters — not age, relationships, or character.",
        "teaser": "The artists starved. Then they revolted.",
        "population": 25,
        "duration_days": 365
    },
    {
        "id": "anonymity",
        "name": "Total Anonymity",
        "rules": "No one has a persistent name or identity. Every day, physical appearances change randomly. You cannot recognize anyone. Reputation does not exist.",
        "teaser": "Trust became the scarcest resource.",
        "population": 25,
        "duration_days": 365
    }
]
```

**Step 5: Commit**

```bash
git add backend/app/api/ backend/app/presets.py
git commit -m "feat: add all API routes with SSE streaming and gallery"
```

---

## Task 10: Frontend — Landing Page

**Files:**
- Create: `frontend/src/views/HomeView.vue`
- Create: `frontend/src/components/RuleEditor.vue`
- Create: `frontend/src/components/PresetCard.vue`
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/styles/main.css`

**Step 1: API client**

Axios-based client + EventSource wrapper for SSE. Methods mirror all backend endpoints. Base URL from `import.meta.env.VITE_API_URL` with fallback to `http://localhost:8000`.

**Step 2: HomeView**

Dark theme (slate-950 bg). Layout:
- Top: "MiroSociety" title + one-line description
- Center: Large textarea (placeholder: "Define the rules of your society...") with example text that cycles
- Below textarea: Population dropdown (10/15/20/25/30/50), Duration dropdown (30/90/180/365 days)
- "Simulate" button (emerald-500, full width under controls)
- Below: "Popular experiments" section header
- Grid of PresetCards (2 columns on mobile, 4 on desktop)

On submit: POST /api/simulate → navigate to `/simulation/{id}`

**Step 3: PresetCard**

Clickable card (slate-900 bg, hover: slate-800, border-l-2 emerald-500 on hover):
- Name in bold (slate-100)
- Teaser in italic (slate-400)
- Click fills textarea with the preset's rules

**Step 4: Styling**

TailwindCSS dark theme. Fonts:
- UI: Inter (via Google Fonts or bundled)
- Narrative text: Georgia (system serif)
Color palette: slate-950/900/800 backgrounds, slate-100/300/400 text, emerald-500 accent, red-500 for conflict, amber-500 for warnings.

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add landing page with rule editor and preset cards"
```

---

## Task 11: Frontend — Simulation View (Main Screen)

**Files:**
- Create: `frontend/src/views/SimulationView.vue`
- Create: `frontend/src/components/SocialGraph.vue`
- Create: `frontend/src/components/NarrativeFeed.vue`
- Create: `frontend/src/components/WorldMetrics.vue`
- Create: `frontend/src/components/TimelineScrubber.vue`
- Create: `frontend/src/components/SpeedControl.vue`
- Create: `frontend/src/components/InjectModal.vue`
- Create: `frontend/src/components/CitizenReveal.vue`

**Step 1: SimulationView — progressive generation flow**

This single view handles BOTH world generation and simulation running.

Phase 1 (generation): Shows world name appearing, citizens revealing one by one (CitizenReveal component), progress text. All driven by SSE events.

Phase 2 (simulation): Seamlessly transitions when first `round_complete` event arrives. Three-panel layout appears:
- Left (30%): SocialGraph + WorldMetrics stacked
- Right (70%): NarrativeFeed
- Bottom bar: TimelineScrubber + SpeedControl
- Top bar: world name, "Day N", speed indicator, [Pause] [Inject] [Fork] buttons

**Step 2: SocialGraph (D3.js force-directed)**

- Nodes = agents. Radius proportional to influence resource. Color by faction (null = slate-500, factions get distinct colors from a palette).
- Edges = relationships. Green solid = positive, red dashed = tension, width = strength.
- On each `round_complete` SSE event: update node positions, add/remove/recolor edges with transitions.
- Click node → open AgentProfile sidebar.
- Tooltip on hover: name + role + emotional state.
- Node pulse animation when agent takes an action this round.

**Step 3: NarrativeFeed**

- Scrollable container (right 70% of screen).
- Each entry: day header (sticky) + time-of-day subheader + narrative text.
- Agent names in narrative are `<span class="agent-link">` — clickable, opens profile.
- Narrative text uses Georgia font, slightly larger than UI text (1.1rem).
- Auto-scroll when live. Manual scroll locks auto-scroll (show "Jump to latest" button).
- Fade-in animation for new entries.
- During fast-forward: show compact summaries instead of full narratives.

**Step 4: WorldMetrics**

5 horizontal progress bars (h-2, rounded):
- Stability (emerald), Prosperity (blue), Trust (violet), Freedom (amber), Conflict (red)
- Label + percentage on right
- Smooth CSS transition on width change (300ms ease)

**Step 5: TimelineScrubber**

- Horizontal range input from day 1 to current day.
- Significant event markers: small dots above the slider at days with high significance.
- Dragging loads historical narratives and agent states from the API.
- Current day indicator when live.

**Step 6: SpeedControl**

Three buttons: [Live] [Fast] [Jump] — toggles speed mode via POST /api/simulation/{id}/speed.
Visual indicator: Live = green dot pulsing, Fast = yellow arrow, Jump = lightning bolt.

**Step 7: InjectModal**

Trigger: "Inject" button in top bar.
Modal (centered, slate-900 bg, backdrop blur):
- Textarea: "What happens next?"
- Submit → POST /api/simulation/{id}/inject → close modal, result appears in narrative feed.

**Step 8: CitizenReveal**

Used during generation phase. Animated card for each citizen as they're generated:
- Name + role appear with typewriter effect
- Personality bars animate from 0 to value
- One-line teaser from background
- Cards arrange in a flowing grid

**Step 9: Commit**

```bash
git add frontend/src/views/SimulationView.vue frontend/src/components/
git commit -m "feat: add simulation view with graph, narrative feed, and controls"
```

---

## Task 12: Frontend — Agent Profile & Interview

**Files:**
- Create: `frontend/src/components/AgentProfile.vue`
- Create: `frontend/src/components/InterviewChat.vue`

**Step 1: AgentProfile**

Slide-in sidebar from right (w-96, slate-900 bg, border-l slate-800):
- Header: Name, role, age, emotional state (with emoji-free indicator — colored dot)
- Quote: italicized line from background
- Section "Personality": 5 horizontal bars with labels
- Section "Believes": bulleted list of current beliefs
- Section "Relationships": list of (name → description), clickable names
- Section "Remembers": core_memory items as a timeline
- Section "Recent": last 10 actions as compact entries (Day N: action description)
- Button: "Interview {name}" → expands InterviewChat

Updates live via SSE when simulation is running.

**Step 2: InterviewChat**

Embedded below profile content when activated:
- Chat bubbles: user (right, emerald bg) and agent (left, slate-800 bg)
- Input field at bottom
- Submit → POST /api/simulation/{sim_id}/agent/{id}/interview
- Response appears as agent bubble with typing indicator
- Conversation history persisted in component state (lost on close)

**Step 3: Commit**

```bash
git add frontend/src/components/AgentProfile.vue frontend/src/components/InterviewChat.vue
git commit -m "feat: add agent profile sidebar with interview chat"
```

---

## Task 13: Frontend — Report & Gallery

**Files:**
- Create: `frontend/src/views/ReportView.vue`
- Create: `frontend/src/views/GalleryView.vue`
- Create: `frontend/src/components/MetricSparkline.vue`
- Create: `frontend/src/components/KeyMoment.vue`
- Create: `frontend/src/components/GalleryCard.vue`

**Step 1: ReportView**

Centered content column (max-w-3xl mx-auto), designed to look good as a standalone shareable page:
- Header: world name + rules as subtitle + stats (N citizens, N days, N events)
- "What Happened": summary paragraph in Georgia serif
- "Key Moments": vertical timeline (line on left, dots at each moment, day number + title + description)
- "Metrics Over Time": 5 MetricSparklines in a row
- "The Surprise": highlighted section (slate-800 bg, border-l-4 emerald-500) with the unexpected emergent behavior
- "Factions": cards for each faction with name, description, peak members
- Footer buttons: [Run Again] [Fork With Changes] [Share Link] [Publish to Gallery]
- Share: copies URL to clipboard. URL is `/report/{id}` which works for public sims.

If viewing a fork: show split-screen comparison with original (side by side key moments + divergent metrics).

**Step 2: MetricSparkline**

SVG component (200x40px). Line chart with filled area under curve (gradient from emerald-500/20 to transparent). No axes, no labels — just the shape. Metric name + final value below.

**Step 3: GalleryView**

Grid of GalleryCards. Top: sort selector (Recent / Most Viewed / Most Forked). Each card:
- World name (bold)
- Rules (truncated, slate-400)
- Teaser from report summary (1 line)
- Stats: N days, N agents, N views, N forks
- Click → navigate to read-only ReportView

**Step 4: Commit**

```bash
git add frontend/src/views/ReportView.vue frontend/src/views/GalleryView.vue frontend/src/components/
git commit -m "feat: add report view, gallery, and sparkline components"
```

---

## Task 14: Fork System

**Files:**
- Create: `backend/app/services/forker.py`
- Modify: `backend/app/api/simulate.py` — add fork endpoint logic

**Step 1: Build fork service**

```python
class SimulationForker:
    def __init__(self, llm: LLMClient, store: SimulationStore): ...

    async def fork(self, source_sim_id: str, fork_at_day: int, changes: str) -> str:
        """
        1. Create new simulation entry (forked_from = source_sim_id)
        2. Copy all state from source up to fork_at_day's last round
        3. LLM interprets the change request:
           "The user wants to change: '{changes}'
            Current agents: {agent_summaries}
            Current world state: {state_summary}
            Describe the specific modifications to make:
            - Agent changes: [{agent_id, field, new_value}]
            - World state changes: [{field, new_value}]
            - Removed agents: [agent_ids]
            - Added agents: [{persona}]"
        4. Apply modifications to the copied state
        5. Return new simulation_id (caller starts engine from the fork point)
        """
```

**Step 2: Commit**

```bash
git add backend/app/services/forker.py
git commit -m "feat: add simulation fork system"
```

---

## Task 15: Integration & Docker

**Files:**
- Modify: `backend/app/main.py` — wire all services, lifespan handler
- Modify: `frontend/src/router/index.js` — all routes
- Create: `Dockerfile`
- Modify: `docker-compose.yml`
- Create: root `package.json` — convenience scripts

**Step 1: Backend integration**

`main.py` lifespan handler:
- On startup: create data directories, init global.db, instantiate LLMClient + SimulationStore + all services
- Store service instances in `app.state`
- Register routers: simulate, agents, gallery, presets

**Step 2: Frontend routing**

```javascript
routes: [
  { path: '/', component: HomeView },
  { path: '/simulation/:id', component: SimulationView },
  { path: '/report/:id', component: ReportView },
  { path: '/gallery', component: GalleryView },
]
```

**Step 3: Docker**

Multi-stage Dockerfile:
```dockerfile
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist backend/static
RUN pip install -e backend/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Backend serves `static/` as static files mount and serves `index.html` for all non-API routes (SPA fallback).

**Step 4: Root package.json convenience scripts**

```json
{
  "scripts": {
    "dev": "concurrently \"npm run backend\" \"npm run frontend\"",
    "backend": "cd backend && uvicorn app.main:app --reload --port 8000",
    "frontend": "cd frontend && npm run dev",
    "setup": "cd backend && pip install -e . && cd ../frontend && npm install"
  }
}
```

**Step 5: Commit**

```bash
git add .
git commit -m "feat: full integration with Docker and convenience scripts"
```

---

## Task 16: Polish & First Demo

**Step 1: Run full flow end-to-end**

```bash
npm run setup
npm run dev
# Open localhost:5173
# Click "Nobody Can Lie" preset
# Click Simulate
# Watch generation → simulation → narrative
# Test inject, speed controls, agent profile, interview
# Let it run to completion
# Check report
```

**Step 2: Fix issues found during demo**

Expected areas needing tuning:
- Agent decision prompt may need iteration (actions too timid, or too chaotic)
- Narrator may need style adjustments (too verbose, not enough dialogue)
- Tension engine thresholds may need calibration
- Reactive micro-round parsing may need fallback handling

**Step 3: Run all 8 presets, save best narrative excerpts**

Use the best moments as example content on the landing page (below the preset cards, as a "Recent highlights" section showing actual simulation output).

**Step 4: Commit**

```bash
git add .
git commit -m "feat: polish and demo-tested with all 8 presets"
```

---

## Execution Order Summary

| Task | What | Dependencies | Est. Time |
|------|------|-------------|-----------|
| 1 | Project scaffold | None | 30 min |
| 2 | Data models | Task 1 | 45 min |
| 3 | Database layer | Task 2 | 1 hr |
| 4 | LLM client | Task 1 | 30 min |
| 5 | World generator | Tasks 2, 4 | 45 min |
| 6 | Citizen generator | Tasks 2, 4 | 1 hr |
| 7 | Simulation engine + tension + resolver | Tasks 2, 3, 4 | 3 hr |
| 8 | Narrator | Tasks 2, 4 | 1 hr |
| 9 | API routes + presets | Tasks 3-8 | 1.5 hr |
| 10 | Frontend: Landing | Task 1 | 1 hr |
| 11 | Frontend: Simulation view | Task 10 | 3 hr |
| 12 | Frontend: Agent profile + interview | Task 11 | 1 hr |
| 13 | Frontend: Report + Gallery | Task 11 | 1.5 hr |
| 14 | Fork system | Tasks 3, 4, 7 | 1 hr |
| 15 | Integration & Docker | Tasks 9-14 | 1 hr |
| 16 | Polish & demo | Task 15 | 2 hr |

**Total estimated: ~19-20 hours**

**Parallelizable:**
- Tasks 3 + 4 (independent backend infra)
- Tasks 5 + 6 (both need 2 + 4, independent of each other)
- Tasks 10-13 (all frontend, only need API contract from Task 9)
- Task 14 (fork system, independent of frontend)

**Critical path:** 1 → 2 → 4 → 7 → 9 → 15 → 16
