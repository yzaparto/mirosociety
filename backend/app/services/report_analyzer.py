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
