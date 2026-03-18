# MiroSociety Discovery Engine — Design Document

> Agents don't just react to your scenario. They tell you what you should have done differently.

## Overview

MiroSociety's simulation already produces rich behavioral data — agent speeches, internal thoughts, abandonment reasons, protest targets. Today that data is narrated but never mined for actionable insights. This design adds a Discovery Engine that extracts counter-proposals and unmet needs from agent behavior, clusters them into named discoveries, and surfaces them in the report as potential what-if scenarios the user can fork and test.

This also addresses the core criticism from the Balanced News review of MiroFish: that multi-agent simulations produce "volume, not insight." By making agents explicitly propose alternatives and mining their behavior for latent signals, MiroSociety's output becomes genuinely actionable — not just a restatement of inputs.

### What Changes

| Before | After |
|--------|-------|
| Agents react to conditions | Agents react AND propose alternatives via `SUGGEST` |
| Report shows what happened | Report shows what happened + what agents wished was different |
| All agents at temperature 0.8 | Per-agent temperature (0.5–1.1) derived from personality |
| Tension engine injects external events in market sims | Internal pressure only for market sims — no confounders |
| Insights require reading narrative | Discoveries surfaced as structured cards with evidence and fork suggestions |

### What Stays the Same

- FEEL → WANT → FEAR → DECIDE agent reasoning chain
- Three-tier memory (core + working + reflective)
- Reactive micro-rounds producing dialogue
- Existing report pipeline (Passes 0–4)
- Fork system and comparison view

---

## 1. The SUGGEST Action

### Purpose

A new action type that lets agents step outside the simulation to propose what the company or society *should* do differently. Distinct from `PROPOSE_RULE` (which changes internal simulation rules) — `SUGGEST` addresses the simulation's designer, not the other agents.

### Availability Gate

`SUGGEST` is only available to agents who have a reason to want something different:

- Agent's `emotional_state` is in `("frustrated", "dissatisfied", "angry", "restless", "conflicted")`
- OR agent took an `ABANDON` or `PROTEST` action in the last 3 rounds (tracked via working memory)

This prevents content agents from inventing problems. Suggestions come from genuine frustration.

### Action Definition

```python
class ActionType(str, Enum):
    # ... existing 17 actions ...
    SUGGEST = "SUGGEST"
```

Args:
```json
{"suggestion": "what the company/society should change", "reason": "why this would help"}
```

### Prompt Addition

Added to `AGENT_DECISION_SYSTEM` in the action args section:

```
- SUGGEST: {{"suggestion": "what the company/society should change", "reason": "why"}}
  (Use this when you believe the rules, product, or approach itself is flawed — not just that
   you disagree with others, but that the system could be designed better)
```

### Resolver Effect

- No world state changes
- No metrics impact
- The suggestion is recorded as a standard `ActionEntry` with `action_type=SUGGEST`
- Agent's `speech` field carries a public version of the suggestion (visible in narrative)
- Tagged for the discovery pipeline

### Conditional Availability in Engine

In `_build_decision_prompt`, the `SUGGEST` action is only included in the available actions list when the agent meets the emotional gate:

```python
eligible_for_suggest = (
    agent.emotional_state in ("frustrated", "dissatisfied", "angry", "restless", "conflicted")
    or any("ABANDON" in m or "PROTEST" in m for m in agent.working_memory[-3:])
)
if not eligible_for_suggest:
    available = [a for a in available if a != ActionType.SUGGEST]
```

---

## 2. Mining Existing Agent Data

### Data Sources

Beyond explicit `SUGGEST` actions, agents leak insights in three existing data streams that are currently recorded but never analyzed:

**Source 1 — Abandonment reasons.** Every `ABANDON` action has `args.reason`. Clustering these produces a ranked list of churn drivers.

**Source 2 — Internal thoughts.** The `internal_thought` field captures what agents think but don't say. Agents who `COMPLY` publicly but privately think "I'm only staying because switching is too hard" are a different signal than genuinely satisfied agents. Internal thoughts from agents who later abandoned are especially valuable — they show the path to churn.

**Source 3 — Protest targets.** Every `PROTEST` action has `args.target`. Clustering these produces a ranked list of friction points.

### Data Collection (ReportAnalyzer — No LLM)

New static method in `ReportAnalyzer`:

```python
@staticmethod
def compute_discoveries(actions: list[ActionEntry], agents: list[AgentPersona]) -> dict:
    # Collect SUGGEST actions
    suggestions = [
        {"agent": a.agent_name, "day": a.day,
         "suggestion": a.action_args.get("suggestion", ""),
         "reason": a.action_args.get("reason", "")}
        for a in actions if a.action_type == ActionType.SUGGEST
    ]

    # Collect ABANDON reasons
    churn_drivers = [
        {"reason": a.action_args.get("reason", ""), "agent": a.agent_name, "day": a.day}
        for a in actions if a.action_type == ActionType.ABANDON and a.action_args.get("reason")
    ]

    # Collect PROTEST targets
    friction_points = [
        {"target": a.action_args.get("target", ""), "agent": a.agent_name, "day": a.day}
        for a in actions if a.action_type == ActionType.PROTEST and a.action_args.get("target")
    ]

    # Cross-reference: internal thoughts from agents who eventually abandoned
    abandoners = {a.agent_id for a in actions if a.action_type == ActionType.ABANDON}
    pre_churn_signals = [
        {"thought": a.internal_thought, "agent": a.agent_name, "day": a.day,
         "action": a.action_type.value}
        for a in actions
        if a.agent_id in abandoners and a.internal_thought
        and a.action_type != ActionType.ABANDON  # thoughts before the abandon
    ]

    return {
        "suggestions": suggestions,
        "churn_drivers": churn_drivers,
        "friction_points": friction_points,
        "pre_churn_signals": pre_churn_signals[-20:],  # cap for prompt size
    }
```

### LLM Synthesis (New Pass 3.5 in Report Pipeline)

A new `DISCOVERY_SYSTEM` prompt takes the raw discovery data and clusters it into 3–7 named discoveries.

```python
DISCOVERY_SYSTEM = """You are analyzing agent behavior from a simulation of {world_name}.
Rules: {rules}

You have been given:
- Explicit suggestions from frustrated agents (SUGGEST actions)
- Reasons agents gave for leaving (ABANDON reasons)
- What agents protested (PROTEST targets)
- Internal thoughts from agents who eventually churned

Cluster these into 3-7 named discoveries. Each discovery represents a distinct
insight that the user could act on.

Return JSON:
{{
  "discoveries": [
    {{
      "title": "Short, punchy title (e.g. 'Loyalty Goes Unrewarded')",
      "description": "2-3 sentences: what the insight is, how many agents expressed it,
                       and why it matters for the user's decision",
      "type": "unmet_need | churn_trigger | hidden_objection | unexpected_advocate | cascade_risk",
      "strength": "strong | moderate | weak",
      "evidence": {{
        "agents": ["names of agents involved"],
        "days": [day numbers],
        "quotes": ["Actual quotes from agents — speeches, thoughts, or suggestion reasons"]
      }},
      "fork_suggestion": "One sentence: what scenario the user could fork-test based on this"
    }}
  ]
}}

Discovery types:
- unmet_need: agents want something that doesn't exist
- churn_trigger: the specific thing that pushed agents to leave
- hidden_objection: agents complied publicly but internally rejected
- unexpected_advocate: a skeptic/competitor-segment agent who converted, and why
- cascade_risk: one agent's action triggered a chain reaction

Strength: strong = 3+ agents independently, moderate = 2 agents, weak = 1 agent with
compelling reasoning.

Only include discoveries with real evidence. Do not invent patterns that aren't in the data."""
```

### Report Integration

The discoveries object is added to the final report alongside existing sections:

```python
return {
    "executive_brief": executive_brief,
    "scorecard": scorecard,
    "insights": insights,
    "discoveries": discoveries,  # NEW
    "segments": segments_final,
    "action_items": pass4.get("action_items", []),
    # ... rest unchanged
}
```

The action synthesis pass (Pass 4) also receives discoveries as input, so action items can reference them: "Based on Discovery #2 (Loyalty Goes Unrewarded), consider launching a retention program before the price change."

---

## 3. Tension Engine Constraints for Market Simulations

### The Problem

The Tension Engine's external event generator produces unrealistic disruptions for market simulations. A solar storm, a plague, or alien contact have nothing to do with a Netflix pricing scenario. Injecting random external events contaminates the experiment — you can't tell whether churn came from the proposed change or the injected event.

### The Fix

For market simulations, disable external events entirely. Only allow internal pressure (natural agent psychology).

#### Market Simulation Behavior

| Mechanism | Enabled | Rationale |
|-----------|---------|-----------|
| `_internal_pressure` | Yes | Agents naturally developing doubt is organic psychology, not noise |
| `_faction_fracture` | Yes | Brand loyalists splitting into sub-factions is a real signal |
| `_external_event` | **No** | External events are confounders that corrupt attribution |

#### Society Simulation Behavior

Everything stays as-is. All three mechanisms enabled.

### Implementation

In `TensionEngine.check_and_apply`, add a market detection flag:

```python
async def check_and_apply(
    self, world_state, agents, recent_actions_significant, is_market: bool = False
) -> tuple[WorldState, list[AgentPersona], str | None]:
    # ... existing stability/quiet checks ...

    if dominant_faction and random.random() < 0.4:
        # Faction fracture — enabled for both
        return await self._faction_fracture(...)

    elif not is_market and (self._quiet_rounds >= 5 or random.random() < 0.5):
        # External events — society only
        return await self._external_event(...)

    else:
        # Internal pressure — enabled for both
        return self._internal_pressure(...)
```

#### Threshold Adjustment for Market Sims

Market opinion shifts slower than town-square drama. For market simulations:

- Stable rounds threshold: 3 → **5** (wait longer before intervening)
- Quiet rounds threshold: 5 → **8** (let the market settle naturally)

```python
stable_threshold = 5 if is_market else 3
quiet_threshold = 8 if is_market else 5

needs_intervention = (
    self._stable_rounds >= stable_threshold
    or self._quiet_rounds >= quiet_threshold
    or market_stagnation
)
```

---

## 4. Per-Agent Temperature for Cognitive Diversity

### The Problem

Every agent decision uses temperature 0.8. A conformist schoolteacher and a volatile rebel produce outputs from the same sampling distribution. Personality traits influence the prompt but not the model's randomness. This means all agents reason similarly — different words, same distribution.

### The Fix

Derive temperature from personality traits.

```python
def agent_temperature(personality: Personality) -> float:
    wildness = (
        (1.0 - personality.conformity) * 0.5
        + personality.confrontational * 0.3
        + personality.ambition * 0.2
    )
    return 0.5 + wildness * 0.6
```

| Agent Type | conformity | confrontational | ambition | Temperature |
|------------|-----------|-----------------|----------|-------------|
| Conformist schoolteacher | 0.9 | 0.1 | 0.3 | 0.62 |
| Moderate pragmatist | 0.5 | 0.4 | 0.5 | 0.78 |
| Rebel activist | 0.1 | 0.9 | 0.8 | 1.00 |
| Quiet skeptic | 0.3 | 0.2 | 0.2 | 0.71 |
| Ambitious opportunist | 0.2 | 0.5 | 0.9 | 0.93 |

### Changes Required

**`LLMClient.generate()`** — add optional `temperature` parameter:

```python
async def generate(self, system, user, json_mode=False, max_tokens=1000,
                   retries=3, temperature: float | None = None) -> str:
    kwargs = {
        "model": self.model,
        "messages": [...],
        "max_tokens": max_tokens,
        "temperature": temperature if temperature is not None else 0.8,
    }
```

**`LLMClient.generate_batch()`** — accept per-prompt temperatures:

```python
async def generate_batch(self, prompts, json_mode=False, max_tokens=1000,
                         temperatures: list[float] | None = None) -> list[str]:
    temps = temperatures or [0.8] * len(prompts)
    tasks = [
        self.generate(system, user, json_mode=json_mode, max_tokens=max_tokens,
                      temperature=t)
        for (system, user), t in zip(prompts, temps)
    ]
    return await asyncio.gather(*tasks)
```

**`SimulationEngine._batch_decisions()`** — compute and pass per-agent temps:

```python
temperatures = [agent_temperature(a.personality) for a in active_agents]
responses = await self.llm.generate_batch(prompts, json_mode=True,
                                          max_tokens=500, temperatures=temperatures)
```

**`SimulationEngine._reactive_micro_round()`** — same pattern for reaction calls.

---

## Implementation Priority

| # | Task | Files Changed | Complexity |
|---|------|---------------|------------|
| 1 | Per-agent temperature | `llm.py`, `engine.py` | Low — ~15 lines |
| 2 | Add `SUGGEST` action type | `action.py`, `engine.py`, `resolver.py` | Low — new enum + prompt line + resolver case |
| 3 | SUGGEST availability gate | `engine.py` (`_build_decision_prompt`) | Low — 5 lines |
| 4 | Tension engine market constraints | `tension.py`, `engine.py` | Low — flag + conditional |
| 5 | `compute_discoveries` in ReportAnalyzer | `report_analyzer.py` | Medium — new method, cross-referencing actions |
| 6 | Discovery synthesis LLM pass | `narrator.py` | Medium — new prompt + integration into report pipeline |
| 7 | Wire discoveries into Pass 4 (action synthesis) | `narrator.py` | Low — add to synthesis context |
| 8 | Report output includes discoveries | `narrator.py` | Low — add to return dict |
| 9 | Frontend: discoveries section in ReportView | `ReportView.vue` | Medium — new card-based section |
