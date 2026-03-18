from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from app.models.action import ActionEntry, ReactiveResponse
from app.models.world import WorldState, WorldMetrics
from app.services.llm import LLMClient, parse_json
from app.constants import TIMES_OF_DAY

if TYPE_CHECKING:
    from app.db.store import SimulationStore

logger = logging.getLogger(__name__)

NARRATE_SYSTEM = """You are a dry, observational narrator documenting life in {world_name}.
Rules of this world: {rules}

Your style is like a nature documentary about humans — factual, specific, occasionally wry:
- Report what people did and said, not what it "felt like"
- Use plain, direct sentences. No purple prose, no dramatic metaphors.
- Include actual quotes when someone spoke. Paraphrase internal thoughts briefly.
- Note contradictions between what people say and what they think.
- One dry observation or ironic aside per scene is fine. No more.
- Do NOT use phrases like "the air was thick with tension" or "a storm was brewing"
- 2-3 short paragraphs max. Shorter is better."""

NARRATE_USER = """Previous update:
{previous_narrative}

What happened during {time_of_day} on Day {day}:
{action_summaries}

{reactions_text}

{tension_event_text}

Summarize what happened. Be specific about who did what and where. Keep it grounded."""

EPOCH_SYSTEM = """You are summarizing a period in the history of {world_name}, a simulated society.
Rules: {rules}

Compress the events into a 2-3 paragraph summary capturing the key developments, shifts in power, emerging conflicts, and notable character moments. Write as a historian, not a novelist."""

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


class Narrator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def narrate_round(
        self,
        world_state: WorldState,
        actions: list[ActionEntry],
        reactions: list[ReactiveResponse] | None = None,
        previous_narrative: str | None = None,
        tension_event: str | None = None,
    ) -> str:
        if not actions:
            return ""

        action_lines = []
        for a in actions:
            line = f"- {a.agent_name}: {a.action_type.value}"
            if a.speech:
                line += f' — said: "{a.speech}"'
            if a.internal_thought:
                line += f" [privately thinks: {a.internal_thought}]"
            if a.action_args:
                details = {k: v for k, v in a.action_args.items() if k != "content"}
                if details:
                    line += f" ({details})"
            action_lines.append(line)

        reactions_text = ""
        if reactions:
            reaction_lines = []
            for r in reactions:
                if r.reaction_type != "silent" and r.content:
                    reaction_lines.append(f"- {r.agent_name} reacted: {r.content}")
            if reaction_lines:
                reactions_text = "Reactions:\n" + "\n".join(reaction_lines)

        tension_text = ""
        if tension_event:
            tension_text = f"A significant event occurred: {tension_event}"

        time_of_day = TIMES_OF_DAY[world_state.round_in_day % len(TIMES_OF_DAY)]

        system = NARRATE_SYSTEM.format(
            world_name=world_state.blueprint.name,
            rules="; ".join(world_state.blueprint.rules),
        )
        user = NARRATE_USER.format(
            previous_narrative=previous_narrative or "This is the beginning of the story.",
            time_of_day=time_of_day,
            day=world_state.day,
            action_summaries="\n".join(action_lines),
            reactions_text=reactions_text,
            tension_event_text=tension_text,
        )

        return await self.llm.generate(system=system, user=user, max_tokens=600)

    async def summarize_epoch(
        self,
        world_name: str,
        rules: list[str],
        narratives: list[str],
        metrics_start: WorldMetrics,
        metrics_end: WorldMetrics,
        day_start: int,
        day_end: int,
    ) -> str:
        system = EPOCH_SYSTEM.format(world_name=world_name, rules="; ".join(rules))
        narrative_text = "\n\n---\n\n".join(narratives[:20])

        metrics_delta = (
            f"Metrics changed from Day {day_start} to Day {day_end}:\n"
            f"  Stability: {metrics_start.stability:.2f} → {metrics_end.stability:.2f}\n"
            f"  Prosperity: {metrics_start.prosperity:.2f} → {metrics_end.prosperity:.2f}\n"
            f"  Trust: {metrics_start.trust:.2f} → {metrics_end.trust:.2f}\n"
            f"  Freedom: {metrics_start.freedom:.2f} → {metrics_end.freedom:.2f}\n"
            f"  Conflict: {metrics_start.conflict:.2f} → {metrics_end.conflict:.2f}\n"
            f"  Brand Sentiment: {metrics_start.brand_sentiment:.2f} → {metrics_end.brand_sentiment:.2f}\n"
            f"  Purchase Intent: {metrics_start.purchase_intent:.2f} → {metrics_end.purchase_intent:.2f}\n"
            f"  Word of Mouth: {metrics_start.word_of_mouth:.2f} → {metrics_end.word_of_mouth:.2f}\n"
            f"  Churn Risk: {metrics_start.churn_risk:.2f} → {metrics_end.churn_risk:.2f}\n"
            f"  Adoption Rate: {metrics_start.adoption_rate:.2f} → {metrics_end.adoption_rate:.2f}"
        )

        user = f"Days {day_start}-{day_end}:\n\n{narrative_text}\n\n{metrics_delta}"
        return await self.llm.generate(system=system, user=user, max_tokens=500)

    async def generate_report(self, simulation_id: str, store: "SimulationStore") -> dict:
        world_state = await store.get_world_state(simulation_id)
        if not world_state:
            return {"error": "No world state found"}

        blueprint = world_state.blueprint
        metrics_history = await store.get_metrics_history(simulation_id)
        all_narratives = await store.get_narratives(simulation_id)
        agents = await store.get_all_agents(simulation_id)
        actions = await store.get_actions(simulation_id)

        proposed_change = await store.get_meta(simulation_id, "proposed_change")
        is_market = proposed_change is not None

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
