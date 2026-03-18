# Analyst Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current single-LLM-call report with a multi-pass analyst report that produces actionable recommendations, interpreted metrics, emergent insights, and segment deep-dives — generated in the background as soon as simulation completes.

**Architecture:** 4-pass pipeline (1 computation pass + 3 LLM passes) in `narrator.py`. Report stored in sim DB. Background generation triggered from `engine.py`. New ReportView with 7 layered sections.

**Tech Stack:** Python/FastAPI (backend), Vue 3 + Tailwind (frontend), aiosqlite (storage), existing LLMClient

---

### Task 1: Add Report Storage to Store

**Files:**
- Modify: `backend/app/db/store.py:45-57` (add report table to `_init_sim_db`)
- Modify: `backend/app/db/store.py` (add new methods at end of file)

**Step 1: Add `report` table to `_init_sim_db`**

In `backend/app/db/store.py`, inside `_init_sim_db()`, after the existing `CREATE TABLE` and `CREATE INDEX` statements (around line 56), add:

```python
await db.execute("CREATE TABLE IF NOT EXISTS report (id INTEGER PRIMARY KEY CHECK (id = 1), status TEXT DEFAULT 'pending', report_json TEXT, error TEXT)")
```

**Step 2: Add report storage methods**

Add these methods to the `SimulationStore` class at the end of the file:

```python
async def set_report_status(self, sim_id: str, status: str, error: str | None = None) -> None:
    async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
        await db.execute(
            "INSERT OR REPLACE INTO report (id, status, error) VALUES (1, ?, ?)",
            (status, error),
        )
        await db.commit()

async def save_report(self, sim_id: str, report: dict) -> None:
    async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
        await db.execute(
            "INSERT OR REPLACE INTO report (id, status, report_json) VALUES (1, 'ready', ?)",
            (json.dumps(report, default=str),),
        )
        await db.commit()

async def get_report(self, sim_id: str) -> dict | None:
    try:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            cursor = await db.execute("SELECT status, report_json, error FROM report WHERE id = 1")
            row = await cursor.fetchone()
            if not row:
                return {"status": "pending"}
            status, report_json, error = row
            if status == "ready" and report_json:
                return {"status": "ready", "report": json.loads(report_json)}
            return {"status": status, "error": error}
    except Exception:
        return {"status": "pending"}
```

**Step 3: Verify**

Run: `cd backend && python -c "from app.db.store import SimulationStore; print('OK')"`
Expected: `OK`

---

### Task 2: Build Pass 1 — Data Aggregation (Pure Computation)

**Files:**
- Create: `backend/app/services/report_analyzer.py`

**Step 1: Create the ReportAnalyzer class**

Create `backend/app/services/report_analyzer.py`:

```python
from __future__ import annotations
import statistics
from collections import defaultdict

from app.models.action import ActionEntry, ActionType
from app.models.agent import AgentPersona
from app.models.world import WorldMetrics


METRIC_LABELS = {
    "stability": "Stability",
    "prosperity": "Prosperity",
    "trust": "Trust",
    "freedom": "Freedom",
    "conflict": "Conflict",
    "brand_sentiment": "Brand Sentiment",
    "purchase_intent": "Purchase Intent",
    "word_of_mouth": "Word of Mouth",
    "churn_risk": "Churn Risk",
    "adoption_rate": "Adoption Rate",
}

INVERSE_METRICS = {"conflict", "churn_risk"}

MARKET_METRICS = {"brand_sentiment", "purchase_intent", "word_of_mouth", "churn_risk", "adoption_rate"}

SOCIAL_METRICS = {"stability", "prosperity", "trust", "freedom", "conflict"}


def _rate(value_100: float, inverse: bool) -> str:
    v = (100 - value_100) if inverse else value_100
    if v >= 81:
        return "excellent"
    if v >= 61:
        return "strong"
    if v >= 41:
        return "moderate"
    if v >= 21:
        return "weak"
    return "critical"


def _trend(start: float, end: float) -> str:
    delta = end - start
    if delta > 0.05:
        return "up"
    if delta < -0.05:
        return "down"
    return "flat"


class ReportAnalyzer:

    @staticmethod
    def compute_metric_stats(metrics_history: list[dict], is_market: bool) -> list[dict]:
        if not metrics_history:
            return []

        active_keys = set(SOCIAL_METRICS)
        if is_market:
            active_keys |= MARKET_METRICS

        results = []
        for key in active_keys:
            values = [m.get(key, 0.5) for m in metrics_history]
            start_val = values[0]
            end_val = values[-1]
            volatility = statistics.stdev(values) if len(values) > 1 else 0.0

            value_100 = round(end_val * 100)
            start_100 = round(start_val * 100)
            inverse = key in INVERSE_METRICS

            results.append({
                "metric": key,
                "label": METRIC_LABELS[key],
                "value": value_100,
                "start_value": start_100,
                "end_raw": end_val,
                "start_raw": start_val,
                "min": round(min(values) * 100),
                "max": round(max(values) * 100),
                "trend": _trend(start_val, end_val),
                "volatility": round(volatility, 4),
                "rating": _rate(value_100, inverse),
                "inverse": inverse,
            })

        return sorted(results, key=lambda x: x["metric"])

    @staticmethod
    def compute_agent_stats(agents: list[AgentPersona], actions: list[ActionEntry]) -> list[dict]:
        action_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        speeches: dict[int, list[str]] = defaultdict(list)
        thoughts: dict[int, list[str]] = defaultdict(list)

        for a in actions:
            action_counts[a.agent_id][a.action_type.value] += 1
            if a.speech:
                speeches[a.agent_id].append(a.speech)
            if a.internal_thought:
                thoughts[a.agent_id].append(a.internal_thought)

        results = []
        for agent in agents:
            results.append({
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "faction": agent.faction,
                "emotional_state": agent.emotional_state,
                "personality": agent.personality.model_dump(),
                "action_counts": dict(action_counts.get(agent.id, {})),
                "speeches": speeches.get(agent.id, [])[-10:],
                "thoughts": thoughts.get(agent.id, [])[-10:],
                "total_actions": sum(action_counts.get(agent.id, {}).values()),
            })
        return results

    @staticmethod
    def compute_segment_stats(agent_stats: list[dict]) -> list[dict]:
        segments: dict[str, list[dict]] = defaultdict(list)
        for a in agent_stats:
            seg_key = a["role"] or "General"
            segments[seg_key].append(a)

        results = []
        for seg_name, seg_agents in segments.items():
            total = len(seg_agents)
            purchased = sum(1 for a in seg_agents if a["action_counts"].get("PURCHASE", 0) > 0)
            abandoned = sum(1 for a in seg_agents if a["action_counts"].get("ABANDON", 0) > 0)
            recommended = sum(1 for a in seg_agents if a["action_counts"].get("RECOMMEND", 0) > 0)
            compared = sum(1 for a in seg_agents if a["action_counts"].get("COMPARE", 0) > 0)

            adopted = purchased - abandoned if purchased > abandoned else 0
            churned = abandoned

            results.append({
                "name": seg_name,
                "agent_count": total,
                "funnel": {
                    "aware": total,
                    "interested": purchased + compared + recommended,
                    "tried": purchased,
                    "adopted": adopted,
                    "churned": churned,
                },
                "adoption_pct": round((adopted / total) * 100) if total > 0 else 0,
                "advocate_count": recommended,
                "top_speeches": [],
                "top_thoughts": [],
            })

            all_speeches = []
            all_thoughts = []
            for a in seg_agents:
                all_speeches.extend(a["speeches"][-3:])
                all_thoughts.extend(a["thoughts"][-3:])
            results[-1]["top_speeches"] = all_speeches[-15:]
            results[-1]["top_thoughts"] = all_thoughts[-15:]

        return results

    @staticmethod
    def detect_inflection_points(metrics_history: list[dict], threshold: float = 0.05) -> list[dict]:
        if len(metrics_history) < 2:
            return []

        points = []
        metric_keys = list(METRIC_LABELS.keys())

        for i in range(1, len(metrics_history)):
            curr = metrics_history[i]
            prev = metrics_history[i - 1]
            round_num = curr.get("round", i)
            day = round_num // 3 + 1

            for key in metric_keys:
                delta = abs(curr.get(key, 0.5) - prev.get(key, 0.5))
                if delta >= threshold:
                    direction = "spike" if curr.get(key, 0.5) > prev.get(key, 0.5) else "drop"
                    points.append({
                        "day": day,
                        "round": round_num,
                        "metric": key,
                        "label": METRIC_LABELS[key],
                        "delta": round(delta, 4),
                        "direction": direction,
                        "value_before": round(prev.get(key, 0.5), 4),
                        "value_after": round(curr.get(key, 0.5), 4),
                    })

        points.sort(key=lambda x: x["delta"], reverse=True)
        return points[:20]

    @staticmethod
    def compute_confidence(metrics_history: list[dict], agent_count: int) -> str:
        rounds = len(metrics_history)
        if rounds >= 30 and agent_count >= 15:
            return "high"
        if rounds >= 15 and agent_count >= 8:
            return "medium"
        return "low"
```

**Step 2: Verify**

Run: `cd backend && python -c "from app.services.report_analyzer import ReportAnalyzer; print('OK')"`
Expected: `OK`

---

### Task 3: Build Passes 2-4 — LLM Analysis in Narrator

**Files:**
- Modify: `backend/app/services/narrator.py:44-71` (replace REPORT_TRENDS_SYSTEM)
- Modify: `backend/app/services/narrator.py:162-266` (replace generate_report)

**Step 1: Add new prompt templates**

In `backend/app/services/narrator.py`, replace the `REPORT_TRENDS_SYSTEM` prompt (lines 44-71) with these three new prompts:

```python
INTERPRET_METRICS_SYSTEM = """You are a senior analyst interpreting simulation results from {world_name}.
Rules of this world: {rules}

Given structured metric stats, epoch summaries, and agent data, produce:

1. Per-metric explanation: One sentence explaining WHY each metric reached its final value. Reference specific events or behaviors.
2. Executive verdict: Should the user proceed (go), proceed with caution (caution), or fundamentally rethink (rethink)?
3. Confidence assessment: Based on simulation length and agent count.
4. 3-5 emergent insights: Things that were NOT predictable from the simulation setup alone. Each must reference specific agents, days, or action patterns as evidence.

Return JSON:
{{
  "executive_brief": {{
    "verdict": "go" | "caution" | "rethink",
    "confidence": "{confidence}",
    "headline": "One sentence verdict",
    "summary": "One paragraph expanding on the verdict"
  }},
  "metric_explanations": {{
    "metric_key": "One sentence explanation"
  }},
  "insights": [
    {{
      "title": "Short hook",
      "description": "2-3 sentences explaining what happened and why it matters for the user's decision",
      "evidence": {{
        "agents": ["agent names involved"],
        "days": [day numbers],
        "actions": ["ACTION_TYPES involved"]
      }},
      "type": "opportunity" | "risk" | "surprise"
    }}
  ]
}}"""

SEGMENT_ANALYSIS_SYSTEM = """You are a market research analyst studying segment reactions in {world_name}.
Rules: {rules}

Given per-segment data (action counts, quotes, personality traits), produce a deep analysis of each segment.

For each segment, provide:
1. Reaction summary: 1-2 sentences on how this segment responded overall
2. Top objection: The most common reason agents in this segment rejected or abandoned (infer from their speeches and thoughts)
3. Champion: The most enthusiastic adopter — name and a short reason why
4. Representative quote: Pick the most insightful actual speech or thought from this segment

Return JSON:
{{
  "segments": [
    {{
      "name": "segment name",
      "reaction": "1-2 sentence reaction summary",
      "top_objection": "The main barrier or complaint",
      "champion": {{"name": "agent name", "why": "Short reason"}},
      "representative_quote": "An actual quote from an agent"
    }}
  ]
}}"""

ACTION_SYNTHESIS_SYSTEM = """You are a strategy consultant synthesizing findings from a simulation of {world_name}.
Rules: {rules}

Given the executive brief, metric interpretations, insights, and segment analysis, produce:

1. 3-7 prioritized action items. Each must be specific and actionable (not vague like "improve marketing"). Reference the simulation evidence that supports it. Include expected impact.
2. Key risks with severity levels.
3. Second-order effects: downstream consequences the user should anticipate.

Return JSON:
{{
  "action_items": [
    {{
      "action": "Specific, concrete thing to do",
      "reasoning": "Evidence from the simulation supporting this",
      "expected_impact": "What changes if this is done",
      "priority": "high" | "medium" | "low"
    }}
  ],
  "risks": [
    {{"risk": "Description", "severity": "high" | "medium" | "low"}}
  ],
  "second_order_effects": ["Effect description"]
}}"""
```

**Step 2: Replace `generate_report` with the new multi-pass pipeline**

Replace the entire `generate_report` method (lines 162-266) with:

```python
async def generate_report(self, simulation_id: str, store: "SimulationStore") -> dict:
    world_state = await store.get_world_state(simulation_id)
    if not world_state:
        return {"error": "No world state found"}

    blueprint = world_state.blueprint
    metrics_history = await store.get_metrics_history(simulation_id)
    all_narratives = await store.get_narratives(simulation_id)
    agents = await store.get_all_agents(simulation_id)
    actions = await store.get_actions(simulation_id)

    is_market = any(
        a.action_type in (ActionType.PURCHASE, ActionType.ABANDON, ActionType.RECOMMEND, ActionType.COMPARE)
        for a in actions
    )

    # --- Pass 0: Epoch summaries (existing logic) ---
    epoch_size = 30
    total_days = world_state.day
    epochs = []

    for start_day in range(1, total_days + 1, epoch_size):
        end_day = min(start_day + epoch_size - 1, total_days)
        epoch_narrs = [n["text"] for n in all_narratives if start_day <= n.get("day", 0) <= end_day]
        if not epoch_narrs:
            continue

        m_start = WorldMetrics()
        m_end = WorldMetrics()
        for m in metrics_history:
            day_of_round = m.get("round", 0) // 3 + 1
            if day_of_round <= start_day:
                m_start = WorldMetrics(**{k: m.get(k, getattr(WorldMetrics(), k)) for k in WorldMetrics.model_fields})
            if day_of_round <= end_day:
                m_end = WorldMetrics(**{k: m.get(k, getattr(WorldMetrics(), k)) for k in WorldMetrics.model_fields})

        summary = await self.summarize_epoch(
            blueprint.name, blueprint.rules, epoch_narrs, m_start, m_end, start_day, end_day
        )
        epochs.append({"days": f"{start_day}-{end_day}", "summary": summary})

    epoch_text = "\n\n".join(f"Days {e['days']}:\n{e['summary']}" for e in epochs)

    # --- Pass 1: Data aggregation (no LLM) ---
    from app.services.report_analyzer import ReportAnalyzer

    metric_stats = ReportAnalyzer.compute_metric_stats(metrics_history, is_market)
    agent_stats = ReportAnalyzer.compute_agent_stats(agents, actions)
    segment_stats = ReportAnalyzer.compute_segment_stats(agent_stats)
    inflection_points = ReportAnalyzer.detect_inflection_points(metrics_history)
    confidence = ReportAnalyzer.compute_confidence(metrics_history, len(agents))

    # --- Pass 2: Metric interpretation + insights ---
    metrics_summary = "\n".join(
        f"- {s['label']}: {s['rating']} ({s['value']}/100), "
        f"started at {s['start_value']}, trend: {s['trend']}, volatility: {s['volatility']}"
        for s in metric_stats
    )
    inflection_summary = "\n".join(
        f"- Day {p['day']}: {p['label']} {p['direction']} by {p['delta']:.2f} "
        f"({p['value_before']:.2f} → {p['value_after']:.2f})"
        for p in inflection_points[:10]
    )
    agent_summary = "\n".join(
        f"- {a['name']} ({a['role']}): {a['total_actions']} actions, "
        f"state={a['emotional_state']}, faction={a['faction'] or 'none'}"
        for a in agent_stats
    )

    system_p2 = INTERPRET_METRICS_SYSTEM.format(
        world_name=blueprint.name,
        rules="; ".join(blueprint.rules),
        confidence=confidence,
    )
    user_p2 = (
        f"Epoch summaries:\n{epoch_text}\n\n"
        f"Metric stats:\n{metrics_summary}\n\n"
        f"Key inflection points:\n{inflection_summary}\n\n"
        f"Agent summary:\n{agent_summary}\n\n"
        f"Total days: {total_days}, Total agents: {len(agents)}, "
        f"Total actions: {len(actions)}"
    )

    response_p2 = await self.llm.generate(system=system_p2, user=user_p2, json_mode=True, max_tokens=2000)
    pass2 = parse_json(response_p2)

    # Build scorecard by merging computed stats with LLM explanations
    explanations = pass2.get("metric_explanations", {})
    scorecard = []
    for s in metric_stats:
        scorecard.append({
            "metric": s["metric"],
            "label": s["label"],
            "rating": s["rating"],
            "value": s["value"],
            "start_value": s["start_value"],
            "trend": s["trend"],
            "explanation": explanations.get(s["metric"], ""),
        })

    # --- Pass 3: Segment analysis ---
    segment_input = ""
    for seg in segment_stats:
        segment_input += f"\n## Segment: {seg['name']} ({seg['agent_count']} agents)\n"
        segment_input += f"Adoption: {seg['adoption_pct']}%, Advocates: {seg['advocate_count']}\n"
        segment_input += f"Funnel: {seg['funnel']}\n"
        if seg["top_speeches"]:
            segment_input += "Recent speeches:\n" + "\n".join(f'  - "{s}"' for s in seg["top_speeches"][-8:]) + "\n"
        if seg["top_thoughts"]:
            segment_input += "Recent thoughts:\n" + "\n".join(f"  - {t}" for t in seg["top_thoughts"][-8:]) + "\n"

    system_p3 = SEGMENT_ANALYSIS_SYSTEM.format(
        world_name=blueprint.name,
        rules="; ".join(blueprint.rules),
    )
    user_p3 = f"Segment data:\n{segment_input}"

    response_p3 = await self.llm.generate(system=system_p3, user=user_p3, json_mode=True, max_tokens=1500)
    pass3 = parse_json(response_p3)

    # Merge LLM segment analysis with computed funnel data
    llm_segments = {s["name"]: s for s in pass3.get("segments", [])}
    segments_final = []
    for seg in segment_stats:
        llm_seg = llm_segments.get(seg["name"], {})
        segments_final.append({
            "name": seg["name"],
            "adoption_pct": seg["adoption_pct"],
            "funnel": seg["funnel"],
            "reaction": llm_seg.get("reaction", ""),
            "top_objection": llm_seg.get("top_objection", ""),
            "champion": llm_seg.get("champion", {"name": "", "why": ""}),
            "representative_quote": llm_seg.get("representative_quote", ""),
        })

    # --- Pass 4: Action synthesis ---
    executive_brief = pass2.get("executive_brief", {})
    insights = pass2.get("insights", [])

    synthesis_context = (
        f"Executive verdict: {executive_brief.get('verdict', 'unknown')} — {executive_brief.get('headline', '')}\n\n"
        f"Key insights:\n" + "\n".join(f"- [{i.get('type', '')}] {i.get('title', '')}: {i.get('description', '')}" for i in insights) + "\n\n"
        f"Segment outcomes:\n" + "\n".join(
            f"- {s['name']}: {s['adoption_pct']}% adoption. {s.get('reaction', '')} Objection: {s.get('top_objection', '')}"
            for s in segments_final
        ) + "\n\n"
        f"Metric scorecard:\n" + "\n".join(
            f"- {s['label']}: {s['rating']} ({s['value']}/100) — {s.get('explanation', '')}"
            for s in scorecard
        )
    )

    system_p4 = ACTION_SYNTHESIS_SYSTEM.format(
        world_name=blueprint.name,
        rules="; ".join(blueprint.rules),
    )

    response_p4 = await self.llm.generate(system=system_p4, user=synthesis_context, json_mode=True, max_tokens=1500)
    pass4 = parse_json(response_p4)

    # --- Assemble final report ---
    # Build narrative section from epoch summaries
    key_moments = []
    for p in inflection_points[:10]:
        key_moments.append({
            "day": p["day"],
            "title": f"{p['label']} {p['direction']}",
            "description": f"{p['label']} shifted from {p['value_before']:.2f} to {p['value_after']:.2f}",
        })

    return {
        "executive_brief": executive_brief,
        "scorecard": scorecard,
        "insights": insights,
        "segments": segments_final,
        "action_items": pass4.get("action_items", []),
        "risks": pass4.get("risks", []),
        "second_order_effects": pass4.get("second_order_effects", []),
        "narrative": {
            "summary": executive_brief.get("summary", ""),
            "key_moments": key_moments,
            "surprise": next((i["description"] for i in insights if i.get("type") == "surprise"), ""),
            "factions": [],
        },
        "metrics_history": metrics_history,
        "meta": {
            "agent_count": len(agents),
            "total_days": total_days,
            "total_actions": len(actions),
            "rules": blueprint.rules,
            "world_name": blueprint.name,
        },
    }
```

**Step 3: Add missing import at top of narrator.py**

Add `from app.models.action import ActionEntry, ReactiveResponse, ActionType` — update the existing import to include `ActionType`.

**Step 4: Verify**

Run: `cd backend && python -c "from app.services.narrator import Narrator; print('OK')"`
Expected: `OK`

---

### Task 4: Trigger Background Report Generation from Engine

**Files:**
- Modify: `backend/app/services/engine.py:305-313` (after simulation_complete event)
- Modify: `backend/app/api/simulate.py:186-191` (update report endpoint)

**Step 1: Add background report trigger in engine.py**

In `backend/app/services/engine.py`, after line 313 (`await self.store.update_status(simulation_id, SimulationStatus.COMPLETED.value)`), add:

```python
asyncio.create_task(self._generate_report_background(simulation_id))
```

Then add this method to the `SimulationEngine` class:

```python
async def _generate_report_background(self, simulation_id: str):
    try:
        await self.store.set_report_status(simulation_id, "generating")
        report = await self.narrator.generate_report(simulation_id, self.store)
        if "error" in report:
            await self.store.set_report_status(simulation_id, "failed", error=report["error"])
        else:
            await self.store.save_report(simulation_id, report)
    except Exception as e:
        logger.error("Report generation failed for %s: %s", simulation_id, e, exc_info=True)
        await self.store.set_report_status(simulation_id, "failed", error=str(e))
```

Note: The engine needs a reference to `self.narrator`. Check how narrator is initialized in the app — it may need to be passed to the engine constructor or accessed via `app.state`.

**Step 2: Update the report endpoint in simulate.py**

Replace the `get_report` endpoint (lines 186-191) with:

```python
@router.get("/simulation/{sim_id}/report")
async def get_report(sim_id: str, request: Request):
    store = request.app.state.store
    result = await store.get_report(sim_id)
    if result.get("status") == "ready":
        return result["report"]
    return result
```

This way:
- If report is ready: returns the full report JSON (same shape as before, backwards compatible)
- If generating: returns `{"status": "generating"}`
- If failed: returns `{"status": "failed", "error": "..."}`
- If pending: returns `{"status": "pending"}`

**Step 3: Ensure engine has narrator access**

Check `backend/app/services/engine.py` constructor. If it doesn't have `self.narrator`, add it. Look at how the engine is instantiated (likely in `main.py` or app startup). The narrator is already on `app.state.narrator`, so either:
- Pass narrator to engine constructor, or
- Pass the narrator when creating the background task

**Step 4: Verify**

Run the backend server and confirm no import errors.

---

### Task 5: Rewrite ReportView.vue Frontend

**Files:**
- Modify: `frontend/src/views/ReportView.vue` (complete rewrite)
- Modify: `frontend/src/api/client.js:74-77` (update getReport for polling)

**Step 1: Update API client for polling**

In `frontend/src/api/client.js`, replace the `getReport` method:

```javascript
async getReport(simulationId) {
    const { data } = await api.get(`/simulation/${simulationId}/report`)
    return data
},

async pollReport(simulationId, interval = 3000, maxAttempts = 60) {
    for (let i = 0; i < maxAttempts; i++) {
        const data = await this.getReport(simulationId)
        if (data.status === 'ready' || data.executive_brief) {
            return data.executive_brief ? data : data.report
        }
        if (data.status === 'failed') {
            throw new Error(data.error || 'Report generation failed')
        }
        await new Promise(r => setTimeout(r, interval))
    }
    throw new Error('Report generation timed out')
},
```

**Step 2: Rewrite ReportView.vue**

Replace the entire contents of `frontend/src/views/ReportView.vue` with the new analyst report layout. The view should have these sections in order:

1. **Loading state** — skeleton loader with "Analyzing simulation results..." when polling
2. **Executive Brief** — colored banner (green/amber/red), headline, summary, confidence badge, meta stats
3. **Scorecard** — 2-3 column grid of metric cards with rating pills, values as X/100, trend arrows, explanations
4. **Key Insights** — cards with colored left borders by type (opportunity=blue, risk=red, surprise=amber), with collapsible evidence tags
5. **Segment Deep-Dive** — per-segment cards with mini funnel bars, reaction, objection, champion, quote
6. **Action Items** — numbered priority cards (High=red, Medium=amber, Low=gray) with what/why/impact
7. **Risks & Effects** — risk cards with severity badges, second-order effects list
8. **Evidence Trail** — collapsible section with narrative, key moments timeline, metric sparklines
9. **Footer actions** — Run Again, Share Link, Publish to Gallery

Key implementation notes:
- Use `onMounted` to call `api.pollReport(route.params.id)` — this handles the polling automatically
- Verdict colors: go = emerald, caution = amber, rethink = red
- Rating pill colors: excellent/strong = emerald, moderate = amber, weak = orange, critical = red
- Funnel visualization: horizontal stacked bar using div widths proportional to funnel counts
- Evidence tags: small pills showing agent names and day numbers, collapsed by default
- Metric sparklines: simple div-based (like current but cleaner — tiny bars in a flex row)
- The view should handle both old report format (for backwards compat with existing sims) and new format (check for `executive_brief` key)

The full template, script, and styles should be written as a single-file Vue component using `<script setup>`, Composition API, and Tailwind classes consistent with the existing app style (dark theme, slate colors, emerald accents).

**Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

---

### Task 6: Wire Up Engine → Narrator Dependency

**Files:**
- Modify: Backend app startup file (likely `backend/app/main.py` or wherever engine is instantiated)

**Step 1: Find where engine is created**

Search for where `SimulationEngine` is instantiated and ensure it has access to both `store` and `narrator`. The engine needs narrator for background report generation.

**Step 2: Pass narrator to engine**

If engine constructor doesn't accept narrator, add it:

```python
class SimulationEngine:
    def __init__(self, store, narrator, llm, ...):
        self.store = store
        self.narrator = narrator
        ...
```

Update the instantiation site to pass narrator.

**Step 3: Verify**

Run: `cd backend && python -c "from app.services.engine import SimulationEngine; print('OK')"`
Expected: `OK`

---

### Task 7: End-to-End Verification

**Step 1: Start backend**

Run: `cd backend && python -m uvicorn app.main:app --reload`
Verify: Server starts without errors

**Step 2: Start frontend**

Run: `cd frontend && npm run dev`
Verify: Dev server starts without errors

**Step 3: Run a test simulation**

1. Create a market simulation with segments
2. Wait for completion
3. Verify report generates in background (check logs for "generating" → "ready" status)
4. Click "View Report" and verify new layout renders
5. Verify: Executive brief shows with verdict color
6. Verify: Scorecard shows metrics as X/100 with ratings and explanations
7. Verify: Insights section appears with typed cards
8. Verify: Segments show funnel data and quotes
9. Verify: Action items are numbered and prioritized
10. Verify: Evidence trail is collapsible

**Step 4: Test backwards compatibility**

Navigate to `/report/{old_sim_id}` for an existing simulation. The view should gracefully handle the old report format (fallback to showing what's available).
