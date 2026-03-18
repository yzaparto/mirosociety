# Analyst Report Design

## Problem

The current report shows raw metric floats (0.4, 0.5) that are meaningless to users doing market research or customer sentiment analysis. A user seeing "brand_sentiment: 0.72" cannot act on that. The report needs to tell users what to do, why, and back it with evidence — not just show numbers.

## Goals

1. **Decision support**: Lead with actionable recommendations (go/no-go, segment targeting, risk mitigation)
2. **Evidence gathering**: Back every claim with traceable data (agent quotes, action counts, timeline events)
3. **Emergent insights**: Surface things the user didn't ask about — unexpected patterns, coalition formation, cascade effects
4. **Background generation**: Report starts building immediately when simulation ends, ready when user clicks "View Report"

## Non-Goals

- Interactive post-report chat (future)
- Agent survey/interview (future)
- PDF/PowerPoint export (future, covered in enterprise strategy)
- Real-time streaming of report sections (future)

## Report Structure (Top to Bottom)

### 1. Executive Brief

Colored banner at the top. Green (go), amber (caution), red (rethink).

- **Headline**: One sentence verdict — "This product launch shows strong potential in 2 of 4 segments, with a critical churn risk in price-sensitive demographics"
- **Summary**: One paragraph expanding on the headline
- **Confidence**: High / Medium / Low — derived from simulation length, agent count, and metric volatility
- **Meta**: Agent count, total days, total events in a subtle row

### 2. Scorecard

Replaces the current raw metric bar charts. Grid of metric cards (2-3 columns).

Each card shows:
- **Metric name** (e.g., "Brand Sentiment")
- **Rating pill**: Critical / Weak / Moderate / Strong / Excellent (color-coded)
- **Value**: Scaled to 0-100 (not 0.0-1.0)
- **Trend**: Arrow + delta from start value (e.g., "↑ from 50")
- **Explanation**: One sentence from the LLM explaining *why* it's at this level

Rating thresholds (on 0-100 scale):
- 0-20: Critical (red)
- 21-40: Weak (orange)
- 41-60: Moderate (amber)
- 61-80: Strong (green)
- 81-100: Excellent (emerald)

For inverse metrics (conflict, churn_risk) the scale is reversed — high values = Critical, low = Excellent.

Market metrics (brand_sentiment, purchase_intent, word_of_mouth, churn_risk, adoption_rate) only shown for market simulations. Social metrics (stability, prosperity, trust, freedom, conflict) always shown.

### 3. Key Insights — "Things You Should Know"

3-5 emergent behaviors the user didn't anticipate. Each insight is a card with:
- **Type badge**: Opportunity (blue) / Risk (red) / Surprise (amber)
- **Title**: Short hook
- **Description**: 2-3 sentences explaining what happened and why it matters
- **Evidence tags**: Collapsible — lists agent names, days, action types that support the claim

Examples:
- "An informal boycott coalition formed on Day 12 when 3 price-sensitive agents independently started discouraging purchases"
- "Your product's strongest advocates are not the target demographic — they're from an adjacent segment you didn't design for"

### 4. Segment Deep-Dive

One card per segment (agents grouped by role/faction). Each card contains:
- **Segment name + adoption percentage**
- **Mini funnel**: Horizontal stacked bar showing Aware → Interested → Tried → Adopted → Churned with counts
- **Reaction summary**: 1-2 sentences on how this segment responded
- **Top objection**: Most common reason for rejection/abandonment (pulled from agent internal_thought and speech)
- **Champion profile**: Who in this segment advocated, and a short quote why
- **Representative quote**: A real agent quote from the simulation

### 5. Action Items

Numbered, prioritized list. Each item is a structured card:
- **Priority badge**: High (red) / Medium (amber) / Low (gray)
- **What to do**: Specific, concrete action
- **Why**: Evidence-backed reasoning
- **Expected impact**: What changes if this action is taken

### 6. Risks & Second-Order Effects

Split into two sub-sections:
- **Risks**: Each with severity badge (High/Medium/Low) and description
- **Second-order effects**: Bullet list of downstream consequences

### 7. Evidence Trail (Collapsible)

Initially collapsed behind a "Show Evidence Trail" toggle. Contains the existing report data restructured:
- **Narrative summary** (current "What Happened")
- **Key moments timeline** (current timeline with dot indicators)
- **Factions** (current faction cards)
- **Metric sparklines** (improved from current bar blocks — still simple div-based, but with better visual treatment)
- **The Surprise** (current surprise callout)

## Backend: Multi-Pass Analysis Pipeline

### Current State

`narrator.generate_report()` does:
1. Load world state, metrics history, narratives
2. Build 30-day epochs, summarize each with LLM (N calls)
3. One big LLM call with `REPORT_TRENDS_SYSTEM` prompt to produce everything
4. Attach metrics_history and meta

Problems: One massive LLM call tries to do too much. Raw metric floats passed to frontend. No structured data analysis before LLM.

### New Pipeline

#### Pass 0: Epoch Summarization (existing, unchanged)

Already happens. Epoch summaries are available when report generation starts.

#### Pass 1: Data Aggregation (no LLM — pure computation)

Runs before any LLM calls. Builds structured stats from raw simulation data.

**Per-metric stats:**
- start_value, end_value, min, max
- trend direction (up/down/flat — based on start vs end with > 5% threshold)
- volatility (standard deviation across the history)
- human_label (Critical/Weak/Moderate/Strong/Excellent based on thresholds)
- value_100 (scaled to 0-100)

**Per-agent stats:**
- Action counts by type (PURCHASE: 3, ABANDON: 1, RECOMMEND: 5, etc.)
- Speeches and internal thoughts (for quote extraction)
- Final emotional state, faction membership
- Personality traits (for segment correlation)

**Per-segment stats (agents grouped by role):**
- Aggregate action counts
- Adoption funnel: count of agents who did PURCHASE (adopted), ABANDON (churned), RECOMMEND (advocates), neither (neutral)
- Top speeches/thoughts from this segment

**Inflection points:**
- Rounds where any metric delta exceeded a threshold (e.g., > 0.05 change in a single round)
- Mapped to day numbers for the timeline

#### Pass 2: Metric Interpretation + Insights (1 LLM call)

**Input:** Structured stats from Pass 1 + epoch summaries

**Prompt asks for:**
- Per-metric: one-sentence explanation of why it reached its final value
- 3-5 emergent insights with evidence references (agent names, days, action types)
- Executive verdict: go/caution/rethink + confidence + headline + summary paragraph

**Output format:** Structured JSON matching the `executive_brief`, `scorecard[].explanation`, and `insights[]` fields.

#### Pass 3: Segment Analysis (1 LLM call)

**Input:** Per-segment agent data (actions, quotes, emotional states, personality traits) + structured stats

**Prompt asks for:**
- Per-segment: reaction summary, top objection, champion profile with quote, representative quote
- Cross-segment dynamics (which segments influenced which)

**Output format:** Structured JSON matching `segments[]` fields. Funnel numbers come from Pass 1 computation, not LLM.

#### Pass 4: Action Synthesis (1 LLM call)

**Input:** Everything from Passes 1-3

**Prompt asks for:**
- Prioritized action items: what to do, why, expected impact, priority
- Key risks with severity
- Second-order effects

**Output format:** Structured JSON matching `action_items[]`, `risks[]`, `second_order_effects[]`.

### LLM Cost

Current: N epoch calls + 1 big report call
New: N epoch calls (unchanged) + 3 focused calls
Net change: +2 LLM calls, but each is smaller and more focused → better quality per call.

## Report Data Structure

```python
{
  "executive_brief": {
    "verdict": "go" | "caution" | "rethink",
    "confidence": "high" | "medium" | "low",
    "headline": "str",
    "summary": "str"
  },
  "scorecard": [{
    "metric": "brand_sentiment",
    "label": "Brand Sentiment",
    "rating": "strong",
    "value": 72,
    "start_value": 50,
    "trend": "up" | "down" | "flat",
    "explanation": "str"
  }],
  "insights": [{
    "title": "str",
    "description": "str",
    "evidence": {
      "agents": ["name1", "name2"],
      "days": [8, 12],
      "actions": ["ABANDON", "RECOMMEND"]
    },
    "type": "opportunity" | "risk" | "surprise"
  }],
  "segments": [{
    "name": "str",
    "adoption_pct": 65,
    "funnel": {
      "aware": 20,
      "interested": 15,
      "tried": 12,
      "adopted": 8,
      "churned": 3
    },
    "reaction": "str",
    "top_objection": "str",
    "champion": {"name": "str", "why": "str"},
    "representative_quote": "str"
  }],
  "action_items": [{
    "action": "str",
    "reasoning": "str",
    "expected_impact": "str",
    "priority": "high" | "medium" | "low"
  }],
  "risks": [{"risk": "str", "severity": "high" | "medium" | "low"}],
  "second_order_effects": ["str"],
  "narrative": {
    "summary": "str",
    "key_moments": [{"day": "int", "title": "str", "description": "str"}],
    "surprise": "str",
    "factions": [{"name": "str", "description": "str", "peak_members": "int"}]
  },
  "metrics_history": [{"round": "int", "stability": "float", "...": "..."}],
  "meta": {
    "agent_count": "int",
    "total_days": "int",
    "total_actions": "int",
    "rules": ["str"],
    "world_name": "str"
  }
}
```

## Async Report Generation

### Trigger

When the simulation engine finishes its last round and status transitions to `completed`, immediately spawn a background task to generate the report.

### New Status Field

`report_status` on the simulation record:
- `pending` — simulation not done yet
- `generating` — report pipeline is running
- `ready` — report is stored and available
- `failed` — report generation errored

### Storage

Report JSON stored in the simulation's SQLite database in a new `report` table (single row, `report_json TEXT`).

### API

`GET /simulation/{sim_id}/report`:
- If `report_status == ready`: return the full report JSON
- If `report_status == generating`: return `{"status": "generating"}`
- If `report_status == failed`: return `{"status": "failed", "error": "..."}`
- If `report_status == pending`: return `{"status": "pending"}`

### Frontend Polling

1. User clicks "View Report" → navigates to `/report/:id`
2. Fetch report endpoint
3. If `ready` → render report
4. If `generating` → show skeleton loader with "Analyzing simulation results..." and poll every 3 seconds
5. On transition to `ready` → fade in the report

## Files Changed

### Backend
- `backend/app/services/narrator.py` — Replace `generate_report()` with multi-pass pipeline. Add `ReportAnalyzer` class with Pass 1 computation. Add new LLM prompt templates for Passes 2-4.
- `backend/app/services/engine.py` — After simulation completes, spawn background report generation task.
- `backend/app/db/store.py` — Add `report` table. Add `save_report()`, `get_report()`, `get_report_status()`, `set_report_status()` methods.
- `backend/app/api/routes.py` (or equivalent) — Update `/simulation/{sim_id}/report` endpoint to check status and return accordingly.

### Frontend
- `frontend/src/views/ReportView.vue` — Complete rewrite with new section structure, polling logic, skeleton loader.
- `frontend/src/api/client.js` (or equivalent) — Update `getReport()` to handle status responses and polling.
