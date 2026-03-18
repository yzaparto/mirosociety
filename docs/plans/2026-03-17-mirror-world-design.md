# MiroSociety Mirror World — Design Document

> Markets are societies. Simulate the society. Predict the market.

## Overview

MiroSociety evolves from a pure social simulation engine into a general-purpose **what-if simulation platform**. Instead of building a separate marketing tool, we extend the existing society simulator to understand that markets are societies — customers talk to each other, form opinions, influence each other, trade, protest (churn), comply (stay loyal), form communities, and defect (switch brands).

The same engine, same memory system, same tension engine, same reactive micro-rounds. Richer input, richer personas, richer output.

### What Changes

| Before | After |
|--------|-------|
| Input: society rules in natural language | Input: unified **Scenario Brief** — society rules OR product/brand scenario |
| Agents: fictional townsfolk | Agents: townsfolk OR customer segments with consumer psychology traits |
| Actions: 13 social actions | Actions: 13 social + 4 market-specific actions |
| Metrics: stability, prosperity, trust, freedom, conflict | Metrics: existing 5 + brand_sentiment, purchase_intent, word_of_mouth, churn_risk, adoption_rate |
| Report: narrative + key moments + sparklines | Report: narrative + per-persona reactions + aggregate insights + recommendations |
| Fork: basic copy-at-day | Fork: first-class what-if branching with comparison view |

### What Stays the Same

- FEEL → WANT → FEAR → DECIDE agent reasoning chain
- Three-tier memory (core + working + reflective)
- Tension engine preventing equilibrium
- Reactive micro-rounds producing dialogue
- Town Square metaphor (locations, resources, factions)
- Progressive generation (zero dead time)
- Vue 3 + FastAPI + SQLite stack

## Unified Input: The Scenario Brief

A single input model handles both social simulations and market scenarios. The user describes:

### 1. The World

Could be a society or a market.

**Society example:**
> A coastal town of 200 people where lying is physically impossible.

**Market example:**
> The premium electric vehicle market in 2026. Tesla dominates with a reputation for innovation, minimalism, and futuristic identity. Rivals include Rivian (adventure/outdoors positioning) and Lucid (luxury/comfort positioning). The customer base is split between tech enthusiasts, luxury buyers, environmentalists, and mainstream adopters.

### 2. The Rules / Context

Social rules OR market dynamics, brand positioning, cultural norms.

**Society example:**
> - No one can speak an untruth
> - Emotions are visible to all

**Market example:**
> - Tesla's brand identity is built on being the "Apple of cars" — premium, minimal, tech-forward
> - Price range: $35K-$120K depending on model
> - Customers buy Tesla partly as an identity statement
> - Strong online community on Reddit, Twitter, owner forums
> - Elon Musk's personal brand is deeply intertwined with Tesla's brand

### 3. The Change (optional)

What's being introduced into this world. This becomes the simulation's inciting event.

**Society example:**
> A new law banning hoarding of more than 3 days' food supply

**Market example:**
> Tesla changes its iconic "T" logo to a more playful, rounded, consumer-friendly logo intended to appeal to mass-market buyers rather than the current niche tech-forward audience.

### 4. The Segments (optional)

If not provided, the citizen generator creates a diverse cast automatically. If provided, the user specifies archetypes with optional detail.

**Society example (omitted):** Let the generator create a diverse town.

**Market example:**
> - Brand loyalists: Current Tesla owners who see ownership as identity
> - First-time buyers: Considering Tesla for the first time, comparing with competitors
> - Tech enthusiasts: Love Tesla for the technology, not the status
> - Luxury buyers: Want premium feel, came from BMW/Mercedes
> - Skeptics: Don't trust Tesla or Musk, watching from the sidelines
> - Casual observers: General public, vaguely aware of Tesla

### Data Model

```python
class ScenarioBrief(BaseModel):
    world_description: str
    rules_or_context: list[str]
    proposed_change: str | None = None
    target_segments: list[SegmentDefinition] | None = None
    population: int = 25
    duration_days: int = 90

class SegmentDefinition(BaseModel):
    name: str
    description: str
    count: int | None = None  # how many agents of this type; auto-distributed if None
```

The existing `/api/simulate` endpoint accepts this. The world generator and citizen generator handle both styles transparently — the LLM prompts are updated to understand market contexts.

## Extended Agent Model

### New Personality Traits

Four new traits capture consumer psychology. For pure society simulations, these default to 0.5 and have negligible effect.

```python
class Personality(BaseModel):
    # Existing social traits
    honesty: float = Field(default=0.5, ge=0.0, le=1.0)
    ambition: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    confrontational: float = Field(default=0.5, ge=0.0, le=1.0)
    conformity: float = Field(default=0.5, ge=0.0, le=1.0)

    # New market traits
    brand_loyalty: float = Field(default=0.5, ge=0.0, le=1.0)
    price_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    social_proof: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty_seeking: float = Field(default=0.5, ge=0.0, le=1.0)
```

**Trait semantics:**

| Trait | Low (0.0) | High (1.0) | Market Effect |
|-------|-----------|------------|---------------|
| `brand_loyalty` | Switches easily | Dies on the hill | Resists DEFECT/ABANDON, more likely to COMPLY |
| `price_sensitivity` | Money is no object | Every penny counts | TRADE decisions weighted by cost, compares value |
| `social_proof` | Independent thinker | Follows the crowd | Decisions influenced by what others say/do in micro-rounds |
| `novelty_seeking` | "If it ain't broke" | Early adopter | More likely to PURCHASE new things, less likely to resist change |

### Segment-to-Trait Mapping

The citizen generator maps user-defined segments to trait ranges:

| Segment | brand_loyalty | price_sensitivity | social_proof | novelty_seeking |
|---------|--------------|-------------------|--------------|-----------------|
| Brand loyalist | 0.8–1.0 | 0.1–0.3 | 0.3–0.5 | 0.2–0.4 |
| First-time buyer | 0.1–0.3 | 0.5–0.7 | 0.6–0.8 | 0.4–0.6 |
| Tech enthusiast | 0.4–0.6 | 0.2–0.4 | 0.2–0.4 | 0.8–1.0 |
| Luxury buyer | 0.5–0.7 | 0.0–0.2 | 0.5–0.7 | 0.3–0.5 |
| Skeptic | 0.0–0.2 | 0.6–0.8 | 0.4–0.6 | 0.1–0.3 |
| Casual observer | 0.1–0.3 | 0.4–0.6 | 0.7–0.9 | 0.3–0.5 |

These are guidelines for the LLM, not hard rules. The citizen generator uses them to inform persona generation.

## Extended Action Types

### Existing Actions with Market Semantics

The 13 existing actions map naturally to market behavior:

| Action | Social Meaning | Market Meaning |
|--------|---------------|----------------|
| `SPEAK_PUBLIC` | Say something publicly | Post a review, share opinion |
| `SPEAK_PRIVATE` | Say something to someone | Word-of-mouth, private recommendation |
| `TRADE` | Exchange resources | Purchase, transact |
| `FORM_GROUP` | Create/join faction | Join brand community, start advocacy group |
| `PROPOSE_RULE` | Propose community rule | Suggest boycott, propose industry standard |
| `VOTE` | Vote on proposal | Support/reject community initiative |
| `PROTEST` | Publicly oppose | Complain publicly, demand reversal of change |
| `COMPLY` | Follow rules | Accept the change, stay loyal |
| `DEFECT` | Break/circumvent rules | Switch to competitor |
| `BUILD` | Create something | Create content, start a side project |
| `MOVE` | Change location | Shift attention to different channel/community |
| `OBSERVE` | Watch and gather info | Lurk, research, wait and see |
| `DO_NOTHING` | Stay quiet | Indifferent, not engaged |

### New Market Actions

```python
class ActionType(str, Enum):
    # ... existing 13 ...
    RECOMMEND = "RECOMMEND"
    PURCHASE = "PURCHASE"
    ABANDON = "ABANDON"
    COMPARE = "COMPARE"
```

**RECOMMEND** — actively recommend the product/brand to others. Stronger than SPEAK_PRIVATE because it carries intent. Triggers a reactive micro-round where the target considers the recommendation.

Args: `{"target_id": agent_id, "product": "what", "reason": "why"}`

Resolver effect: Target's working memory gets "X recommended Y to me because Z." Nudges target's `purchase_intent` based on relationship quality and target's `social_proof` trait.

**PURCHASE** — buy the product, renew subscription, commit financially.

Args: `{"product": "what", "amount": N}`

Resolver effect: Reduces agent's goods/resources. Increments world `purchase_intent` and `adoption_rate`. Agent's core memory gets "I bought X on day Y."

**ABANDON** — explicitly stop using the product. Stronger than DEFECT because it's a conscious exit, not a rule-break.

Args: `{"product": "what", "reason": "why"}`

Resolver effect: Increments `churn_risk`. Agent's core memory gets "I left X because Y." If the reason is spoken publicly, triggers reactive micro-round (social contagion risk).

**COMPARE** — publicly compare the product with a competitor. Neither positive nor negative — an analytical action.

Args: `{"product_a": "what", "product_b": "what", "verdict": "which is better and why"}`

Resolver effect: Nudges `word_of_mouth`. Witnesses update their beliefs based on the comparison and their own `social_proof` trait.

### Action Availability Rules

Market actions follow the same location-gating pattern as existing actions:

- `PURCHASE` available at `commerce` locations
- `RECOMMEND` requires another agent nearby
- `ABANDON` available anywhere (it's an internal decision)
- `COMPARE` available at `public` and `social` locations

For pure society simulations, these actions are excluded from the available action list (the engine checks whether the world has market context).

## Extended Metrics

```python
class WorldMetrics(BaseModel):
    # Existing social metrics
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    prosperity: float = Field(default=0.5, ge=0.0, le=1.0)
    trust: float = Field(default=0.5, ge=0.0, le=1.0)
    freedom: float = Field(default=0.5, ge=0.0, le=1.0)
    conflict: float = Field(default=0.2, ge=0.0, le=1.0)

    # New market metrics
    brand_sentiment: float = Field(default=0.5, ge=0.0, le=1.0)
    purchase_intent: float = Field(default=0.5, ge=0.0, le=1.0)
    word_of_mouth: float = Field(default=0.0, ge=0.0, le=1.0)
    churn_risk: float = Field(default=0.2, ge=0.0, le=1.0)
    adoption_rate: float = Field(default=0.0, ge=0.0, le=1.0)
```

### Metric Update Rules

Added to `ActionResolver._update_metrics`:

| Action | brand_sentiment | purchase_intent | word_of_mouth | churn_risk | adoption_rate |
|--------|----------------|-----------------|---------------|------------|---------------|
| RECOMMEND | +0.01 | +0.02 | +0.03 | -0.01 | +0.01 |
| PURCHASE | +0.02 | +0.01 | +0.01 | -0.02 | +0.03 |
| ABANDON | -0.05 | -0.03 | +0.02 | +0.05 | -0.02 |
| COMPARE | ±0 (neutral) | ±0 | +0.02 | ±0 | ±0 |
| PROTEST (market) | -0.03 | -0.02 | +0.03 | +0.03 | -0.01 |
| COMPLY (market) | +0.01 | +0.01 | ±0 | -0.01 | +0.02 |
| DEFECT (market) | -0.04 | -0.02 | +0.01 | +0.04 | -0.02 |

For pure society simulations, market metrics stay at defaults and are hidden from the UI.

## World Generator Updates

The world generator prompt is extended to handle market scenarios. When the input describes a product/brand context rather than social rules, the generator creates:

### Market-Appropriate Locations

| Location Type | Examples |
|---------------|----------|
| `public` | Social media plaza, Town square, Public forum |
| `commerce` | Brand store, Competitor showroom, Online marketplace |
| `social` | Coffee shop, Owner meetup spot, Influencer lounge |
| `governance` | Consumer advocacy office, Brand HQ (for brand reps) |
| `residential` | Private homes (where word-of-mouth happens) |

### Market-Appropriate Resources

Instead of `food, goods, influence, knowledge`:
- `money` — purchasing power
- `influence` — social reach, follower count
- `satisfaction` — current happiness with the product
- `information` — how much they know about alternatives
- `loyalty_points` — accumulated investment in the brand (switching cost)

### Market-Appropriate Initial Tensions

Instead of "Privacy vs transparency":
- "Brand identity vs mass appeal"
- "Innovation vs familiarity"
- "Premium positioning vs accessible pricing"
- "Loyal customer expectations vs new customer acquisition"

## Citizen Generator Updates

### Cast Prompt Extension

The `CAST_SYSTEM_PROMPT` is extended with market-aware instructions:

When the world describes a market/product scenario, generate a cast of customers, not townsfolk. Each citizen represents a real consumer archetype:

- If the user provided `target_segments`, generate agents matching those segments with the specified distribution
- If not, auto-generate a diverse cast covering: loyalists, skeptics, newcomers, influencers, competitors' customers, indifferent observers

Citizens get market-relevant roles instead of "Baker" or "Scholar":
- "Tesla Model 3 owner since 2022"
- "Automotive journalist covering EVs"
- "Former BMW owner considering an EV"
- "Reddit power user, r/teslamotors moderator"
- "Rivian reservation holder"

### Persona Prompt Extension

The `PERSONA_SYSTEM_PROMPT` adds market personality traits:

```
Personality scores (market):
- brand_loyalty: 1.0 = ride-or-die fan, 0.0 = switches at a whim
- price_sensitivity: 1.0 = every penny matters, 0.0 = money is no object
- social_proof: 1.0 = does what everyone else does, 0.0 = proudly contrarian
- novelty_seeking: 1.0 = first in line for anything new, 0.0 = hates change
```

Beliefs become brand/market beliefs:
- "Tesla is the best EV on the market"
- "The logo is part of why I bought this car"
- "Elon Musk's vision is what makes Tesla special"
- "I'd switch to Rivian if they had better range"

Goals become consumer goals:
- "Get the best value for my next car purchase"
- "Stay current with the latest technology"
- "Signal my success to my peers"

## Engine Updates

### Agent Decision Prompt

The `AGENT_DECISION_SYSTEM` prompt template is extended with market context when the simulation is market-flavored:

```
THE MARKET CONTEXT:
{market_description}

THE PROPOSED CHANGE:
{proposed_change}

YOUR RELATIONSHIP WITH THE BRAND:
{brand_relationship}

WHAT OTHERS ARE SAYING:
{market_chatter}
```

The engine detects whether the simulation has market context (presence of `proposed_change` in the scenario brief or market-specific locations) and includes these additional prompt sections.

### Active Agent Selection — Market Dynamics

The `_select_active_agents` method gets additional market-relevant weighting:

- Agents with high `brand_loyalty` are more likely to activate when the change first drops (they care deeply)
- Agents with high `social_proof` activate when `word_of_mouth` metric is high (buzz draws them in)
- Agents with high `novelty_seeking` activate early (first responders)
- Agents with high `price_sensitivity` activate when `PURCHASE` actions happen nearby (price discussion triggers them)

### Tension Engine — Market Stagnation Prevention

The tension engine already prevents social equilibrium. For market scenarios, it also prevents:

- **Unanimous acceptance** — if `adoption_rate` > 0.85 for 3 rounds, seed doubt in 2-3 agents ("Am I just following the crowd?", "What did I actually lose in this change?")
- **Unanimous rejection** — if `churn_risk` > 0.85 for 3 rounds, introduce a positive signal (a celebrity endorsement, a price drop, a competitor stumble)
- **Echo chambers** — if all agents at a location share the same sentiment, inject a contrarian voice

## Report Pipeline — Market Report

### Extended Report Sections

The existing 3-stage report pipeline (epoch summaries → trend extraction → report composition) is extended with market-specific sections.

**Stage 3 (report composition) output:**

#### 1. Scenario Restatement
- What is changing
- Who is affected
- What behavior is expected to change
- Derived from the scenario brief input

#### 2. Persona Gallery
- Each distinct segment with representative agent
- Their motivation, pain points, what they value
- Derived from citizen generator output

#### 3. Per-Persona Reaction Analysis
For each segment/archetype, aggregated from simulation data:

**A. Immediate Reaction** (from first 3 days of simulation)
- Dominant emotional state across the segment
- Representative quote (actual `speech` from simulation)

**B. Behavioral Trajectory** (from full simulation)
- What actions they took most (COMPLY, PROTEST, DEFECT, PURCHASE, ABANDON)
- How their behavior evolved over time

**C. Friction Points**
- What they protested or resisted
- What beliefs shifted negatively

**D. Outcome Probabilities**
- Brand perception change: derived from final `brand_sentiment` per segment
- Purchase likelihood change: derived from `purchase_intent` per segment
- Loyalty impact: derived from `churn_risk` per segment

#### 4. Aggregate Insights
- % adopted / % neutral / % rejected — from `adoption_rate` and action counts
- Key positive drivers — actions and events that improved metrics
- Key risks — actions and events that damaged metrics
- Second-order effects — emergent behaviors the LLM identifies from action logs

#### 5. Scenario Simulations (if forked)
- Best-case timeline vs worst-case timeline
- Social reaction simulation (what was said publicly, meme-worthy moments)
- Divergence point — where the timelines split and why

#### 6. Recommendations
- LLM synthesis: should you proceed?
- What to change before launch
- Messaging strategy (informed by what resonated with agents)
- Rollout strategy (gradual vs instant, based on simulation dynamics)

## Fork System — What-If Branching

### Completing the Existing Fork

The fork API exists (`POST /simulation/{id}/fork`). What's missing:

1. **Fork button in SimulationView** — add [Fork] to the control bar alongside [Pause] [Inject] [Stop]
2. **Fork dialog** — modal asking: "Fork at day ___. What changes?" with quick-preset options
3. **Branch comparison view** — split-screen showing original and forked timelines with diverging metrics
4. **Diff narrative** — LLM-generated comparison: "In the original timeline, loyalists held firm. In the fork where the competitor launched simultaneously, even loyalists wavered."

### Quick-Fork Presets for Market Scenarios

Common what-if branches:
- "What if the price was 20% higher/lower?"
- "What if a competitor launched the same day?"
- "What if we did a gradual rollout instead?"
- "What if we kept the old option available?"
- "What if an influencer publicly endorsed/criticized it?"

These are just pre-filled `changes` strings for the existing fork endpoint.

## New Presets

Added to the 8 existing society presets:

### 9. Tesla Logo Change
> Tesla announces a playful new logo to appeal to mainstream buyers.
> 
> Teaser: "The subreddit burned for 72 hours. Then something unexpected happened."

### 10. Netflix Price Hike
> Netflix raises prices by 40% while adding ads to the basic tier.
> 
> Teaser: "They all said they'd cancel. Most didn't. But the ones who did..."

### 11. Apple Removes the Port
> Apple removes the last physical port from the iPhone. Everything is wireless.
> 
> Teaser: "The pros raged. The casuals shrugged. Then the pros bought it anyway."

### 12. New Competitor Enters
> A well-funded startup launches a product that's 30% cheaper with 80% of the features of the market leader.
> 
> Teaser: "Good enough is the most dangerous phrase in business."

### 13. Brand Crisis
> The CEO of a beloved brand is caught in a scandal. The product hasn't changed. The person behind it has.
> 
> Teaser: "They loved the brand. They hated the founder. They couldn't separate the two."

## API Changes

### Modified Endpoints

```
POST /api/simulate
  Body: ScenarioBrief (replaces plain rules text)
  - world_description: str (required)
  - rules_or_context: list[str] (required)
  - proposed_change: str | None
  - target_segments: list[SegmentDefinition] | None
  - population: int = 25
  - duration_days: int = 90
```

Backwards compatible: if `proposed_change` and `target_segments` are null, behaves exactly like before.

### New Endpoints

```
GET /api/simulation/{id}/segments
  Returns: per-segment aggregate metrics and reaction summary
  Used by: report view, comparison view

GET /api/simulation/{id}/compare/{fork_id}
  Returns: side-by-side metrics and narrative diff between original and fork
  Used by: fork comparison view
```

## Frontend Changes

### Simulation Input Page

The rule editor expands to a scenario brief editor:
- **World** textarea (existing, relabeled)
- **Rules / Context** list input (existing, relabeled)
- **The Change** textarea (new, optional, collapsible)
- **Segments** list builder (new, optional, collapsible) — each segment has name + description + optional count
- Population and duration controls (existing)
- Preset cards (existing + new market presets)

### Simulation View

- **Fork button** added to control bar
- **Fork dialog** — day picker + change description + quick-preset buttons
- **Market metrics panel** — brand_sentiment, purchase_intent, word_of_mouth, churn_risk, adoption_rate sparklines (shown only for market simulations)
- **Segment filter** on the social graph — color-code agents by segment

### Report View

- **Segment breakdown tab** — per-segment reaction analysis
- **Comparison tab** — appears when forks exist, shows split-screen timeline
- **Recommendation section** — actionable advice at the bottom

## Implementation Priority

### Phase 1: Core Model Extensions (foundation)
1. Extend `Personality` with 4 market traits
2. Add 4 new `ActionType` values
3. Extend `WorldMetrics` with 5 market metrics
4. Add `ScenarioBrief` and `SegmentDefinition` models
5. Update resolver with market action handling and metric updates

### Phase 2: Generator Updates (intelligence)
6. Update world generator prompts for market scenarios
7. Update citizen generator prompts for market personas and segment mapping
8. Update engine decision prompt with market context
9. Update active agent selection with market trait weighting
10. Update tension engine with market stagnation rules

### Phase 3: Report & Fork (output)
11. Extend report pipeline with market-specific sections
12. Add fork UI (button, dialog, comparison view)
13. Add per-segment aggregation endpoint
14. Add branch comparison endpoint and diff narrative

### Phase 4: Frontend & Presets (polish)
15. Update input page with scenario brief editor
16. Add market metrics to simulation view
17. Add segment visualization to social graph
18. Add 5 market presets
19. Add comparison tab to report view
