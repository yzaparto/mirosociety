# MiroSociety — Design Document

> Define the rules of a society. Watch what emerges.

## Overview

MiroSociety is a multi-agent simulation engine where users define social rules in natural language, and the system generates a small town of AI agents who live under those rules. The simulation runs day by day, and emergent behaviors — institutions, conflicts, workarounds, cultural norms — arise organically from agent interactions.

## Core Decisions

- **Simulation model:** Town Square — agents interact through speech, trade, voting, forming groups, protesting, complying, defecting. Not social media.
- **Scale:** Configurable, default 20-30 agents. Self-hosted can scale to 200+.
- **Agent reasoning:** Round-robin with memory. Each round, a context-dependent subset of agents (5-10) get LLM calls. Others update passively. Crisis = more active agents. Quiet day = fewer.
- **No OASIS dependency:** Custom lightweight simulation engine. OASIS is designed for social media platforms — we need richer action types.
- **No Zep dependency:** Users define worlds from scratch via natural language. No document extraction needed.

## Architecture

```
Frontend (Vue 3 + Vite + D3.js)
    ↕ REST + SSE (Server-Sent Events for live streaming)
Backend (Python + FastAPI)
    ├── World Generator (rules → blueprint)
    ├── Citizen Generator (blueprint → agent personas)
    ├── Simulation Engine (round-by-round loop)
    │   ├── Tension Engine (prevents equilibrium stagnation)
    │   └── Reactive Micro-Rounds (agent conversations within rounds)
    ├── Narrator (actions → readable prose)
    └── Report Generator (multi-stage pipeline → shareable summary)
State Layer (SQLite + JSON files)
    ├── World state (locations, resources, institutions)
    ├── Agent state (beliefs, relationships, tiered memory)
    └── Action log (JSONL)
```

## Data Models

### World Blueprint (generated from user rules)
```json
{
  "name": "Truthtown",
  "description": "A coastal town where lying is physically impossible",
  "rules": ["No one can speak an untruth", "Emotions are visible to all"],
  "locations": [
    {"id": "town_square", "name": "Town Square", "type": "public", "description": "..."},
    {"id": "market", "name": "Market", "type": "commerce", "description": "..."},
    {"id": "council_hall", "name": "Council Hall", "type": "governance", "description": "..."}
  ],
  "resources": ["food", "goods", "influence", "knowledge"],
  "initial_tensions": ["Privacy vs transparency", "Commerce vs fairness"],
  "time_config": {
    "total_days": 365,
    "rounds_per_day": 3,
    "active_agents_per_round_min": 3,
    "active_agents_per_round_max": 10
  }
}
```

### Agent Persona
```json
{
  "id": 0,
  "name": "Elena Vasquez",
  "role": "Baker",
  "age": 34,
  "personality": {
    "honesty": 0.9,
    "ambition": 0.4,
    "empathy": 0.8,
    "confrontational": 0.2,
    "conformity": 0.5
  },
  "background": "Third-generation baker who values routine and community...",
  "goals": ["Protect her livelihood", "Maintain friendships", "Stay out of politics"],
  "core_memory": ["I co-founded the Privacy Council", "Tomás was exiled on day 89"],
  "working_memory": ["Marcus called an emergency meeting this morning"],
  "beliefs": ["Privacy should be protected", "The council has too much power"],
  "relationships": {"3": "Marcus — I respect him but fear his rigidity", "7": "Tomás — I distrust him deeply"},
  "resources": {"food": 80, "goods": 20, "influence": 30, "knowledge": 40},
  "location": "market",
  "faction": null,
  "emotional_state": "uneasy"
}
```

### Action Types
```
SPEAK_PUBLIC     - Say something in a public location
SPEAK_PRIVATE    - Say something to a specific person
TRADE            - Exchange resources with another agent
FORM_GROUP       - Create or join a faction/institution
PROPOSE_RULE     - Propose a new community rule
VOTE             - Vote on a proposal
PROTEST          - Publicly oppose a rule or institution
COMPLY           - Follow a rule (even if unhappy)
DEFECT           - Break or circumvent a rule
BUILD            - Create something (shop, school, wall)
MOVE             - Go to a different location
OBSERVE          - Watch and gather information
DO_NOTHING       - Stay quiet this round
```

### Action Log Entry (JSONL)
```json
{
  "round": 141,
  "day": 47,
  "time_of_day": "morning",
  "agent_id": 0,
  "agent_name": "Elena Vasquez",
  "location": "council_hall",
  "action_type": "SPEAK_PUBLIC",
  "action_args": {
    "content": "I support privacy rights. Yesterday a customer asked if my bread was fresh and I had to say it was from Tuesday."
  },
  "speech": "I support privacy rights.",
  "internal_thought": "I wonder if Marcus is losing control of this council.",
  "targets": [],
  "world_state_changes": {},
  "relationship_changes": {}
}
```

## Agent Memory Architecture

Three-tier memory, inspired by human cognition:

### 1. Core Memory (always in prompt, ~200 tokens)
Permanent facts the agent carries with them. Updated only when something truly significant happens (a relationship fundamentally changes, an institution is created, someone is exiled, a new rule passes). The LLM decides what "promotes" from working memory to core memory via the `memory_promotion` field in each decision.

### 2. Working Memory (recent, ~300 tokens)
Last 2-3 days of events the agent directly witnessed or participated in. Rolling window — old events drop off unless promoted to core memory.

### 3. Reflective Memory (periodic compression)
Every 30 simulated days, a single LLM call per agent: "Given everything that's happened, update your core beliefs, goals, and key memories." This compresses 30 days of lived experience into updated core memory. Cost: 25 agents × 1 call per 30 days = negligible.

## Narrative Tension Engine

LLMs trend toward consensus and resolution. Left unchecked, agents will form a council, agree on norms, and settle into boring equilibrium by day 30. The tension engine prevents this.

The engine maintains a "tension floor" — a minimum level of unresolved conflict. If world metrics show stability > 0.85 and conflict < 0.15 for 3 consecutive rounds:

1. **Internal pressure:** 2-3 agents' emotional states shift to "restless" or "dissatisfied." A latent grievance is added to their beliefs ("I've been overlooked," "the system benefits others more than me," "I'm tired of following rules that don't serve me").

2. **External pressure:** The engine generates a minor environmental event — resource scarcity, a stranger arrives, a natural disaster, a rumor spreads, a neighboring community makes contact.

3. **Faction fracture:** If a dominant faction has >60% of agents, the engine seeds a splinter ideology within it — a subset of members who agree with the faction's goals but disagree on methods.

This models the reality that human societies are never truly at equilibrium. There are always new pressures, generational shifts, and dissatisfied minorities.

## Simulation Loop (per round)

1. Compute context: current day, time, recent events, active disputes, world metrics
2. Check tension engine: if equilibrium detected, generate pressure
3. Determine active agents: base count from config, boosted by crisis/event proximity
4. For each active agent (concurrently via asyncio):
   a. Build agent prompt: persona + core memory + working memory + beliefs + relationships + situation + actions
   b. LLM returns: feel/want/fear reasoning + action + speech + internal thought + belief updates + memory promotion
   c. Parse and validate action
5. **Reactive micro-rounds:** If any SPEAK_PUBLIC or SPEAK_PRIVATE actions occurred, witnesses get lightweight LLM calls to react (agree, disagree, respond, stay silent). This produces conversations, not monologues.
6. Apply all actions to world state (resolve conflicts, update resources, update relationships)
7. Narrator LLM: convert round actions into readable prose paragraph
8. Update agent memories (working memory window, core memory promotions)
9. Update world metrics (stability, prosperity, trust, freedom, conflict) via exponential moving average
10. Log everything to JSONL + SQLite
11. Emit SSE event to frontend

## Agent Decision Prompt (revised)

```
You are {name}, a {age}-year-old {role} in {world_name}.

THE RULES OF THIS WORLD:
{rules}

WHO YOU ARE:
{background}
{personality_description}

WHAT YOU KNOW TO BE TRUE (core memories):
{core_memory}

WHAT YOU BELIEVE RIGHT NOW:
{beliefs}

YOUR RELATIONSHIPS:
{key_relationships}

WHAT JUST HAPPENED (recent days):
{working_memory}

THE SITUATION RIGHT NOW:
You are at {location}. It is {time_of_day} on day {day}.
{immediate_context}

AVAILABLE ACTIONS:
{action_list}

Think step by step:
1. FEEL: What is your emotional reaction to the current situation?
2. WANT: Given your personality and goals, what do you want right now?
3. FEAR: What could go wrong? What worries you?
4. DECIDE: What action do you take?

Respond as JSON:
{
  "feel": "one sentence emotional reaction",
  "want": "one sentence desire",
  "fear": "one sentence concern",
  "action": "ACTION_TYPE",
  "args": { ... },
  "speech": "what you say out loud, if anything (null if silent)",
  "internal_thought": "what you think but don't say",
  "belief_updates": ["any changed beliefs"],
  "memory_promotion": "a core fact to remember long-term, or null"
}
```

## Reactive Micro-Rounds

After primary actions resolve, if any SPEAK_PUBLIC or SPEAK_PRIVATE actions occurred:

1. Identify agents who witnessed the speech act (same location for public, target for private)
2. For each witness, lightweight LLM call (~50 tokens):
   "You just heard {speaker} say '{content}'. React: (a) respond publicly, (b) whisper to someone, (c) stay silent. Return letter + optional one-sentence response."
3. Resolve reactive actions
4. Include reactions in the narrator's round summary

Cost: ~3-5 extra cheap LLM calls per round. Produces natural dialogue instead of disconnected monologues.

## Narrator Prompt (per round)

```
You are narrating events in a small town called {world_name}.
Rules of this world: {rules}

The following actions occurred during {time_of_day} on Day {day}:
{action_summaries_with_speech_and_reactions}

Previous narrative (for continuity):
{previous_narrative}

Write a 2-4 paragraph narrative of what happened, as if writing a novel.
Focus on the most dramatic or consequential events.
Include dialogue where agents spoke. Show reactions and body language.
Contrast what characters say with what they think (use italics for thoughts).
Capture the mood and tension.
Do not editorialize or explain the rules — just tell the story.
```

## Report Generation Pipeline

Multi-stage pipeline (NOT a single LLM call):

### Stage 1: Epoch Summaries
The narrator already generates round narratives. Group into 30-day epochs. One LLM call per epoch: "Summarize the key events and trends of days {N} to {N+30}." Produces ~12 epoch summaries for a year-long simulation.

### Stage 2: Trend Extraction
Feed all epoch summaries + metrics timelines to LLM. Extract: key turning points, faction evolution, surprising emergent behaviors, overall narrative arc.

### Stage 3: Report Composition
Feed trend extraction + the most dramatic individual narratives (selected by highest conflict/change scores) to LLM for final report:
1. One-paragraph summary ("what happened")
2. Key moments (5-10 most consequential events with day numbers)
3. Metric sparklines (stability, freedom, conflict over time)
4. "The Surprise" — the most unexpected emergent behavior
5. Faction summary — what groups formed and why

Total: ~15 LLM calls instead of 1 impossible call.

## Simulation Speed Modes

### Live Mode (default at start)
Every round gets full LLM reasoning + narration. ~5 seconds per round. Good for the first 10-20 days when the user is engaged.

### Fast-Forward Mode
Skip narration for "quiet" rounds. Run agent decisions but only narrate rounds with high significance scores (conflict spike, faction change, proposal, defection). Quiet periods get a one-line summary: "Days 45-52: A quiet week. Market activity normal. No disputes." ~1 second per round.

### Jump Mode
"Skip to the next interesting thing." Engine runs rounds silently until a significance threshold is crossed (conflict spike, new faction, rule change, exile, death, etc.), then drops back to Live Mode. The timeline scrubber shows which days had significant events as highlighted marks.

## Fork System

At any point in the timeline, users can "Fork here" on any day. This creates a copy of the simulation state at that point. The user describes what changes:

- "What if Elena had voted against the Privacy Council?"
- "What if the trader Tomás was never born?"
- "What if the drought happened 3 months earlier?"

The fork runs from that point with the altered condition. The report view can show BOTH timelines side by side — original and fork — highlighting where they diverge.

Implementation: Copy the simulation's SQLite file at the fork point. Modify the specified agent/world state via LLM interpretation. Resume the engine from that round. Frontend shows split-screen comparison.

## Frontend Screens

1. **Landing / Rule Editor** — text input + presets + population/duration config
2. **Simulation View** — generation phase streams seamlessly into simulation (NO separate loading page). Left panel: social graph (D3) + world metrics. Right panel: narrative feed. Bottom: timeline scrubber with speed controls.
3. **Agent Profile** — slide-in sidebar with personality, relationships, beliefs, memory, action history, interview chat
4. **Summary Report** — shareable page with narrative + key moments + sparklines + surprise + fork comparison
5. **Community Gallery** — public simulations browsable by recency, views, forks

## Progressive Generation (Zero Dead Time)

The entire pipeline streams from the moment the user clicks Simulate:

- Second 0-5: "Imagining your world..." → world name + description appear
- Second 5-15: "Populating..." → citizens appear one by one (streamed as generated)
- Second 15-20: "Day 1 begins..." → first round narrative streams in
- Second 20+: Simulation running, new content every 3-5 seconds

The user NEVER sees a blank loading screen. Generation smoothly transitions into simulation on the same page. Citizens are generated in two batches: first 10 immediately (enough to start the sim), remaining generated in background while first rounds run.

## Tech Stack

### Backend
- Python 3.11+
- FastAPI + uvicorn
- OpenAI SDK (any OpenAI-compatible provider)
- SQLite (via aiosqlite)
- Pydantic v2

### Frontend
- Vue 3 (Composition API)
- Vite
- D3.js (social graph)
- TailwindCSS

### Infrastructure
- Docker + Docker Compose
- Single .env for config (LLM provider, model, API key)

## API Endpoints

```
POST /api/simulate              — rules text → starts full pipeline (generate world + citizens + begin simulation), returns simulation_id
GET  /api/simulation/{id}/stream — SSE stream of all events (generation progress, citizen reveals, round narratives, metrics)
GET  /api/simulation/{id}/state  — current world state + metrics
GET  /api/simulation/{id}/agents — all agent states
GET  /api/agent/{sim_id}/{id}    — single agent detail + memory + history
POST /api/agent/{sim_id}/{id}/interview — chat with agent in character
POST /api/simulation/{id}/inject — inject "what if" event into running sim
POST /api/simulation/{id}/fork   — fork simulation at a specific day with altered conditions
POST /api/simulation/{id}/speed  — change speed mode (live / fast-forward / jump)
POST /api/simulation/{id}/pause  — pause simulation
POST /api/simulation/{id}/resume — resume simulation
POST /api/simulation/{id}/stop   — stop simulation, trigger report generation
GET  /api/simulation/{id}/report — get generated report
POST /api/simulation/{id}/publish — make simulation public in gallery
GET  /api/gallery                — list public simulations (sort: recent, views, forks)
GET  /api/gallery/{id}           — read-only view of public simulation report
POST /api/gallery/{id}/fork      — fork a public simulation with modified rules
GET  /api/presets                — list preset scenarios
```

## Presets

1. **Nobody Can Lie** — "Lying is physically impossible. Everyone speaks only truth."
   Teaser: "They invented silence clubs by month 3."

2. **Full Communism** — "No private property. All resources are communal. No one can own more than they need."
   Teaser: "It worked. Then it didn't."

3. **Everyone Is Armed** — "Every citizen carries a weapon. Violence is always an option."
   Teaser: "Politeness became a survival skill."

4. **Total Surveillance** — "Everyone can see what everyone else is doing at all times. No secrets."
   Teaser: "The most powerful person was the one who stopped watching."

5. **Direct Democracy** — "Every decision, no matter how small, must be voted on by everyone."
   Teaser: "They voted 47 times on day 1. By day 30, nobody showed up."

6. **No Phones, No Internet** — "Communication is face-to-face only. No long-distance messaging."
   Teaser: "Rumors moved slower but hit harder."

7. **Absolute Meritocracy** — "Your social status is strictly determined by measurable output. Nothing else."
   Teaser: "The artists starved. Then they revolted."

8. **Total Anonymity** — "No one has a name or persistent identity. You can't be recognized."
   Teaser: "Trust became the scarcest resource."
