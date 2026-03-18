# Agent Research Tools — Design Document

> Agents that can look things up and seek out answers on their own, not just react to what's in front of them.

## Overview

MiroSociety agents currently reason from personality, memories, and what they observe within the simulation. They have no way to acquire new external information or deliberately interrogate other agents. This design adds two new action types — `RESEARCH` (web search) and `INVESTIGATE` (agent-to-agent directed interview) — that let agents ground their decisions in real-world facts and intentionally gather intelligence from peers.

### What Changes

| Before | After |
|--------|-------|
| Agents reason only from internal state + simulation context | Agents can search the web for real facts (prices, reviews, news) |
| Agent-to-agent interaction is random (proximity-based) | Agents can deliberately seek out specific agents to ask pointed questions |
| All opinions are LLM confabulation | Opinions can be grounded in actual search results |
| Information spreads only through speech and observation | Information spreads through active investigation |

### What Stays the Same

- FEEL → WANT → FEAR → DECIDE reasoning chain
- Three-tier memory (core + working + reflective)
- Reactive micro-rounds
- One action per agent per round (research competes with acting — opportunity cost)
- Existing action types and resolver logic

---

## 1. New Action Types

### RESEARCH — Web Search

Agent formulates a search query. The engine runs a real web search via DuckDuckGo, summarizes results through the agent's personality lens, and injects findings into working memory.

**Args:** `{"query": "what to search for", "reason": "why"}`

**Resolver effect:** +3 knowledge resource. No metrics impact. Findings stored in `action_args["findings"]`.

### INVESTIGATE — Agent-to-Agent Directed Interview

Agent targets a specific other agent with a pointed question. The target answers in-character (can lie, deflect, or refuse based on personality). Both agents get working memory entries.

**Args:** `{"target_id": agent_id, "question": "what to ask"}`

**Resolver effect:** +2 knowledge for investigator. Relationship update for both agents. Target's response stored in `action_args["response"]`.

---

## 2. Research Service

New `ResearchService` class in `services/research.py`.

**Search backend:** `duckduckgo-search` Python package — free, no API key.

**Flow:**
1. Call DuckDuckGo with agent's query, get raw snippets + URLs
2. LLM summarizes results through the agent's personality lens (price-sensitive consumer vs brand loyalist take away different things from the same results)
3. Returns 2-3 sentence digest injected into working memory

**Summarization prompt personalizes results per agent:**
- Cites specific numbers, names, facts from search results
- Notes tension if results contradict agent's beliefs
- Notes reinforcement if results confirm agent's beliefs

**Rate limiting:** Max 5 web searches per round across all agents. Agents who don't get a slot get "Wanted to research X but didn't get to it" in working memory.

---

## 3. Engine Integration

### Modified Round Loop

```
select agents → decide → resolve → fulfill research (NEW) → reactive micro-round → narrate → advance
```

`_fulfill_research` is a post-resolve async step (like the existing reactive micro-round):
- RESEARCH actions: call `ResearchService.web_search()`, inject findings into working memory
- INVESTIGATE actions: run target-agent interview LLM call, inject Q&A into both agents' memory

### Investigation Prompt

Target agent answers in-character. Personality drives honesty of response:
- High honesty → truthful even if uncomfortable
- Low honesty → may deflect, lie, or give partial answers
- High confrontational → may push back on the question
- High empathy → considers impact of answer

---

## 4. Prompt Changes

### Decision Prompt Additions

New action args in `AGENT_DECISION_SYSTEM`:
```
- RESEARCH: {"query": "...", "reason": "..."}
- INVESTIGATE: {"target_id": agent_id, "question": "..."}
```

### Behavior Rules Additions

Both social and market behavior rules get:
- "Before forming strong opinions, consider whether you actually KNOW the facts or are just assuming."
- "If someone makes a claim you doubt, you can INVESTIGATE them directly or RESEARCH the claim."

---

## 5. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_ENABLED` | `true` | Toggle web search on/off |
| `MAX_SEARCHES_PER_ROUND` | `5` | Cap on web searches per tick |

---

## Implementation Priority

| # | Task | Files | Complexity |
|---|------|-------|------------|
| 1 | Add `RESEARCH` + `INVESTIGATE` to `ActionType` | `action.py` | Trivial |
| 2 | Create `ResearchService` | `services/research.py` (new) | Medium |
| 3 | Add resolver cases | `resolver.py` | Low |
| 4 | Add `_fulfill_research` + `_run_investigation` to engine | `engine.py` | Medium |
| 5 | Wire into round loop + update prompts | `engine.py` | Low |
| 6 | Config values + dependency + main.py wiring | `config.py`, `pyproject.toml`, `main.py` | Low |
