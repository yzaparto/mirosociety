<p align="center">
  <h1 align="center">MiroSociety</h1>
  <p align="center">
    <strong>Define the rules of a society. Watch what emerges.</strong>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> •
    <a href="#how-it-works">How It Works</a> •
    <a href="#presets">Presets</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#api">API</a> •
    <a href="#deployment">Deployment</a> •
    <a href="#contributing">Contributing</a>
  </p>
</p>

---

MiroSociety is a multi-agent simulation engine that lets you write the rules of a world in plain English and watch AI agents live under them. Emergent behavior — institutions, conflicts, alliances, revolts, quiet compliance — arises from nothing but your rules and agent personalities.

It runs two modes:

- **Society simulations** — build a town with rules like *"lying is impossible"* or *"absolute meritocracy"* and watch social structures emerge over hundreds of simulated days.
- **Market simulations** — define a brand scenario like *"Netflix raises prices by 40%"*, add customer segments, and observe how sentiment, purchase intent, and loyalty shift over time.

Every agent has a personality, memories, beliefs, and relationships. They speak, trade, form groups, propose rules, protest, comply, defect — or do nothing. No script. No predefined outcomes.

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- An OpenAI-compatible API key

### Setup

```bash
git clone https://github.com/your-username/mirosociety.git
cd mirosociety

# Copy env and add your API key
cp .env.example .env

# Install everything
npm run setup

# Start dev servers (backend on :8000, frontend on :5173)
npm run dev
```

Open `http://localhost:5173` and describe your world.

### Docker

```bash
docker compose up --build
```

Single container, port 8000, everything included.

## How It Works

```
  You write rules          AI generates a world       Agents make decisions
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│ "Lying is         │    │ World: Veritas       │    │ Day 1, Morning:     │
│  physically       │───▶│ Locations: Town Hall, │───▶│ Elena SPEAKS_PUBLIC │
│  impossible"      │    │   Market, Temple...  │    │ Marcus TRADES       │
│                   │    │ 25 citizens generated │    │ Dara PROPOSES_RULE  │
└──────────────────┘    └──────────────────────┘    └─────────────────────┘
                                                              │
                              ┌────────────────┐              │
                              │ Tension Engine  │◀─────────────┘
                              │ injects events, │
                              │ splinter groups,│
                              │ internal crises │
                              └────────────────┘
```

Each simulation tick:

1. **Select agents** — a context-dependent subset acts each round
2. **Decide** — each agent reasons over personality, memories, relationships, and world state to pick an action
3. **Resolve** — actions update the world (resources move, relationships shift, metrics change)
4. **Narrate** — prose is generated from raw actions
5. **Tension check** — if the world is stagnating, the tension engine injects pressure (events, factions, crises)

Agents have three tiers of memory: **core** (permanent identity), **working** (recent events), and **reflective** (beliefs that evolve). This prevents loops and creates genuine drift over time.

## Presets

Built-in scenarios to try immediately:

### Society

| Preset | What happens |
|--------|-------------|
| **Nobody Can Lie** | Lying is physically impossible. Emotions are visible. *They invented silence clubs by month 3.* |
| **Full Communism** | No private property. Resources allocated by council. *It worked. Then it didn't.* |
| **Direct Democracy** | Every multi-person decision requires a community vote. *They voted 47 times on day 1.* |
| **No Phones, No Internet** | All communication is face-to-face only. *Rumors moved slower but hit harder.* |
| **Absolute Meritocracy** | Status determined solely by productive output. *The artists starved. Then they revolted.* |
| **Total Anonymity** | No persistent identity. Appearances change daily. *Trust became the scarcest resource.* |

### Market

| Preset | Scenario |
|--------|----------|
| **Tesla Logo Change** | Tesla swaps its iconic logo for a mass-market friendly design |
| **Netflix Price Hike** | 40% price increase + ads on basic tier + password sharing crackdown |
| **Apple Removes the Port** | The last physical port is gone. Everything wireless. |
| **New Competitor Enters** | A startup launches at 30% cheaper with 80% of the features |
| **CEO Scandal** | Beloved founder caught in a major scandal. Product unchanged. |

## Features

- **Natural language rules** — describe any society or market scenario in plain English
- **Live simulation streaming** — watch events unfold in real time via SSE
- **Agent interviews** — ask any agent questions and get in-character responses
- **Event injection** — introduce crises, resource scarcity, or policy changes mid-simulation
- **Fork & compare** — branch a simulation at any point, change the rules, compare timelines
- **Speed control** — live narration, fast-forward, or jump ahead
- **Analyst reports** — auto-generated executive briefs with verdict (go / caution / rethink), metric breakdowns, and insights
- **Gallery** — publish and browse community simulations
- **Customer segments** — define distinct audience personas for market simulations

## Architecture

```
mirosociety/
├── backend/                    # Python / FastAPI
│   └── app/
│       ├── main.py             # App entry, lifespan, CORS, SPA serving
│       ├── config.py           # Settings via pydantic-settings
│       ├── constants.py        # Time periods, emotional states
│       ├── presets.py           # Built-in scenarios
│       ├── api/
│       │   ├── simulate.py     # Core simulation endpoints
│       │   ├── agents.py       # Agent inspection & interview
│       │   ├── gallery.py      # Public simulation gallery
│       │   └── presets.py      # Preset listing
│       ├── db/
│       │   └── store.py        # SQLite persistence (aiosqlite)
│       ├── models/
│       │   ├── agent.py        # AgentPersona, Personality
│       │   ├── world.py        # WorldBlueprint, WorldState, WorldMetrics
│       │   ├── action.py       # ActionType enum, AgentDecision
│       │   └── simulation.py   # Status, SSE events, fork/speed models
│       └── services/
│           ├── llm.py              # OpenAI-compatible LLM client
│           ├── world_generator.py  # Rules → world blueprint
│           ├── citizen_generator.py # Blueprint → agent personas
│           ├── engine.py           # Main simulation loop
│           ├── tension.py          # Anti-stagnation: events, factions
│           ├── resolver.py         # Decisions → world state updates
│           ├── narrator.py         # Actions → prose narratives
│           └── report_analyzer.py  # Metrics & trend analysis
├── frontend/                   # Vue 3 / Vite
│   └── src/
│       ├── views/
│       │   ├── HomeView.vue        # Rules input, presets, launch
│       │   ├── SimulationView.vue  # Live map + event feed
│       │   ├── ReportView.vue      # Analyst report
│       │   ├── GalleryView.vue     # Community gallery
│       │   └── CompareView.vue     # Fork comparison
│       ├── components/             # AgentDetailPanel, MoodDot, Modals...
│       ├── api/client.js           # Axios HTTP + EventSource SSE
│       └── utils/                  # Mood mapping, formatting, metrics
├── docker-compose.yml
├── Dockerfile                  # Multi-stage (Node build + Python runtime)
└── render.yaml                 # One-click Render deploy
```

### Backend Services

| Service | Responsibility |
|---------|---------------|
| `WorldGenerator` | Transforms natural language rules into a structured `WorldBlueprint` with locations, resources, initial tensions, and time configuration |
| `CitizenGenerator` | Creates diverse `AgentPersona` instances with distinct personalities (honesty, ambition, empathy, confrontational, conformity), backgrounds, and initial beliefs |
| `SimulationEngine` | Orchestrates the round loop: select active agents → prompt for decisions → resolve → narrate → check tensions → advance time |
| `TensionEngine` | Prevents equilibrium by injecting external events, spawning splinter factions, and applying internal psychological pressure when metrics flatten |
| `ActionResolver` | Maps agent decisions to concrete world state changes — resource transfers, relationship updates, metric shifts, institutional changes |
| `Narrator` | Converts raw action data into readable prose and generates summary narratives for fast-forward mode |
| `ReportAnalyzer` | Computes statistical trends, generates executive briefs, and produces go/caution/rethink verdicts for market scenarios |

### Agent Action Space

Agents choose from these actions each round based on their personality, context, and the world rules:

| Action | Description |
|--------|-------------|
| `SPEAK_PUBLIC` | Address the community |
| `SPEAK_PRIVATE` | Private conversation |
| `TRADE` | Exchange resources |
| `FORM_GROUP` | Create an organization |
| `PROPOSE_RULE` | Suggest a new community rule |
| `VOTE` | Vote on proposals |
| `PROTEST` | Public dissent |
| `COMPLY` | Follow the rules |
| `DEFECT` | Break the rules |
| `BUILD` | Create infrastructure |
| `OBSERVE` | Watch and learn |
| `PURCHASE` | Buy a product *(market mode)* |
| `ABANDON` | Leave a brand *(market mode)* |
| `RECOMMEND` | Recommend to others *(market mode)* |
| `COMPARE` | Evaluate alternatives *(market mode)* |
| `DO_NOTHING` | Wait |

### Data Flow

```
          ┌─────────────┐
          │  Vue 3 SPA   │
          │              │
          │  HomeView    │──── POST /api/simulate ────▶┐
          │  SimView     │◀─── SSE /stream ────────────┤
          │  ReportView  │──── GET /api/.../report ───▶│
          └─────────────┘                              │
                                                       ▼
                                              ┌─────────────────┐
                                              │    FastAPI       │
                                              │                 │
                                              │  SimulationEngine│
                                              │       │         │
                                              │  ┌────▼────┐    │
                                              │  │ LLMClient│───▶ OpenAI API
                                              │  └─────────┘    │
                                              │       │         │
                                              │  ┌────▼────┐    │
                                              │  │ SQLite   │    │
                                              │  └─────────┘    │
                                              └─────────────────┘
```

The frontend communicates via REST for commands and **Server-Sent Events** for live simulation streaming. Event types include `world_ready`, `citizen_generated`, `round_complete`, `narrative`, `metrics_update`, `injection_result`, and `simulation_complete`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | **Python** · FastAPI · Pydantic · aiosqlite |
| LLM | **OpenAI SDK** (works with any OpenAI-compatible API) |
| Frontend | **Vue 3** (Composition API) · Vue Router · Axios |
| Visualization | **D3.js** force-directed agent graphs |
| Styling | **Tailwind CSS** · dark theme |
| Streaming | **SSE** via sse-starlette |
| Build | **Vite** · multi-stage Docker |
| Deploy | Docker Compose · Render |

## API

### Simulation Lifecycle

```
POST   /api/simulate                         # Start a new simulation
GET    /api/simulation/{id}/stream           # SSE event stream
GET    /api/simulation/{id}/state            # Current world state
POST   /api/simulation/{id}/pause            # Pause
POST   /api/simulation/{id}/resume           # Resume
POST   /api/simulation/{id}/stop             # Stop
POST   /api/simulation/{id}/speed            # Set speed mode
POST   /api/simulation/{id}/inject           # Inject an event
POST   /api/simulation/{id}/fork             # Fork timeline
GET    /api/simulation/{id}/compare/{fid}    # Compare fork vs original
GET    /api/simulation/{id}/report           # Analyst report
POST   /api/simulation/{id}/publish          # Publish to gallery
```

### Agents

```
GET    /api/simulation/{id}/agents           # List all agents
GET    /api/simulation/{id}/agent/{aid}      # Agent details
POST   /api/simulation/{id}/agent/{aid}/interview  # Interview agent
```

### Discovery

```
GET    /api/gallery                           # Browse public simulations
GET    /api/gallery/{id}                      # Gallery item details
GET    /api/presets                            # List built-in presets
```

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | — | Your OpenAI (or compatible) API key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | Model to use for agent reasoning |
| `DATABASE_DIR` | `./data` | SQLite database directory |
| `MAX_CONCURRENT_LLM_CALLS` | `10` | Concurrency limit for LLM requests |

Works with any OpenAI-compatible API: OpenAI, Anthropic (via proxy), Ollama, vLLM, LiteLLM, Together AI, etc.

## Deployment

### Docker Compose (recommended)

```bash
cp .env.example .env
# Edit .env with your API key
docker compose up --build
```

### Render

Click **New Web Service** → connect your repo → Render auto-detects `render.yaml`. Add your `LLM_API_KEY` as a secret environment variable.

### Manual

```bash
# Backend
cd backend
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (dev)
cd frontend
npm install && npm run dev

# Frontend (production)
npm run build
# Built files go to frontend/dist — FastAPI serves them as static
```

## Development

```bash
# Run both servers with hot reload
npm run dev

# Backend only
npm run backend

# Frontend only
npm run frontend

# Build frontend for production
npm run build
```

The Vite dev server proxies `/api` requests to the backend at `localhost:8000`.

## Project Philosophy

- **Rules in, behavior out** — you never script agent behavior; you set constraints and watch
- **Anti-stagnation by design** — the tension engine ensures societies don't just reach peaceful equilibrium; there's always pressure
- **Three-tier memory** — core identity is stable, working memory is recent, beliefs evolve; this prevents repetitive loops
- **Town square, not social media** — agents interact face-to-face in shared spaces, not through feeds; this changes everything about how information spreads
- **Same engine, two modes** — society and market simulations share the same agent loop; market mode just adds consumer-specific actions and metrics

## Contributing

Contributions are welcome. Here's how to get started:

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/my-feature`)
3. **Make your changes** and test locally
4. **Submit a pull request** with a clear description of what changed and why

### Roadmap

MiroSociety is evolving from a simulation sandbox into a **calibrated decision intelligence platform** — grounded in real data, not just plausible fiction. Here's where contributions matter most:

#### Grounding in Reality
- **Calibration data pipeline** — let users upload CSV/PDF (NPS scores, survey data, CRM exports) to seed agent personas from real customer segments instead of pure LLM invention
- **Backtesting framework** — simulate events that already happened (Netflix password crackdown, Twitter → X rebrand) and measure predicted vs actual outcomes to build trust in the engine
- **Monte Carlo batch runner** — run the same scenario 50 times with trait variation and produce confidence intervals instead of single-run narratives

#### Discovery Engine
- **SUGGEST action type** — let frustrated agents propose what the company/society *should* do differently, not just react
- **Behavioral mining** — cluster abandonment reasons, protest targets, and internal thoughts from agents who eventually churned to surface actionable insights
- **Discovery cards in reports** — structured insight cards (unmet needs, churn triggers, hidden objections, cascade risks) with agent quotes as evidence and fork suggestions

#### Agent Intelligence
- **Per-agent LLM temperature** — derive sampling temperature from personality traits so a conformist schoolteacher and a volatile rebel don't reason from the same distribution
- **Market-aware tension engine** — disable external event injection for market simulations (they're confounders), keep only internal psychological pressure and faction fractures
- **Memory and belief drift** — improvements to the three-tier memory system (core → working → reflective) to produce more realistic long-term behavior

#### Enterprise Output
- **PDF/PPTX export** — polished reports with executive summary, per-segment analysis, confidence intervals, and recommendations
- **Fork comparison UI** — split-screen timeline comparison with synced metrics, divergence analysis, and recommendation deltas
- **Multi-fork matrix** — compare 3–5 scenarios side by side in a board-ready table

#### Infrastructure
- **PostgreSQL migration** — replace SQLite for multi-tenant concurrent writes
- **Task queue** — Celery/Redis for batch runs and async report generation
- **API connectors** — Brandwatch, Qualtrics, Salesforce integrations to pull real customer data directly
- **Test coverage** — the codebase needs tests across services, API routes, and frontend components

## License

MIT

---

<p align="center">
  <sub>Built with FastAPI, Vue 3, and curiosity about what happens when you let AI agents make their own choices.</sub>
</p>
