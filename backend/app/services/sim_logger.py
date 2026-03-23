from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.agent import AgentPersona
from app.models.action import ActionEntry, ActionType
from app.models.world import WorldMetrics

logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


class SimulationLogger:
    def __init__(self, sim_id: str):
        self._sim_id = sim_id
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self._path = LOGS_DIR / f"{sim_id}.jsonl"
        try:
            self._fh = open(self._path, "a", encoding="utf-8")
        except OSError as exc:
            logger.warning("SimulationLogger: cannot open %s: %s", self._path, exc)
            self._fh = None

    def _write(self, record: dict[str, Any]):
        if not self._fh:
            return
        try:
            self._fh.write(json.dumps(record, default=str) + "\n")
            self._fh.flush()
        except Exception as exc:
            logger.debug("SimulationLogger write error: %s", exc)

    def log_round(
        self,
        *,
        round_num: int,
        day: int,
        time_of_day: str,
        agents: list[AgentPersona],
        entries: list[ActionEntry],
        metrics: WorldMetrics,
        coherence_scores: dict[int, Any] | None = None,
        personality_mandates: dict[int, str] | None = None,
        cross_agent_repeated: str = "",
    ):
        action_map: dict[int, list[ActionEntry]] = {}
        for e in entries:
            action_map.setdefault(e.agent_id, []).append(e)

        agent_records = []
        abandon_count = 0
        defect_count = 0
        sentiment_dist = {"negative": 0, "positive": 0, "neutral": 0}

        for agent in agents:
            agent_entries = action_map.get(agent.id, [])
            p = agent.personality

            for ae in agent_entries:
                if ae.action_type == ActionType.ABANDON:
                    abandon_count += 1
                elif ae.action_type == ActionType.DEFECT:
                    defect_count += 1
                if ae.speech:
                    lower = ae.speech.lower()
                    neg_kw = {"frustrated", "disappointed", "betrayed", "cancel",
                              "leaving", "ridiculous", "greed", "overpriced"}
                    pos_kw = {"love", "great", "worth", "enjoy", "staying", "loyal"}
                    has_neg = any(kw in lower for kw in neg_kw)
                    has_pos = any(kw in lower for kw in pos_kw)
                    if has_neg and not has_pos:
                        sentiment_dist["negative"] += 1
                    elif has_pos and not has_neg:
                        sentiment_dist["positive"] += 1
                    else:
                        sentiment_dist["neutral"] += 1

            coh_score = None
            if coherence_scores and agent.id in coherence_scores:
                cs = coherence_scores[agent.id]
                coh_score = round(cs.score, 2) if hasattr(cs, "score") else None

            mandate_str = ""
            if personality_mandates and agent.id in personality_mandates:
                mandate_str = personality_mandates[agent.id][:200]

            rec = {
                "id": agent.id,
                "name": agent.name,
                "personality": {
                    "brand_loyalty": round(p.brand_loyalty, 2),
                    "price_sensitivity": round(p.price_sensitivity, 2),
                    "conformity": round(p.conformity, 2),
                    "social_proof": round(p.social_proof, 2),
                    "novelty_seeking": round(p.novelty_seeking, 2),
                },
                "emotional_state": agent.emotional_state,
                "actions": [
                    {
                        "type": ae.action_type.value,
                        "speech": (ae.speech[:120] if ae.speech else None),
                    }
                    for ae in agent_entries
                ],
                "coherence_score": coh_score,
                "has_abandoned": list(agent.abandoned_products),
                "has_defected": agent.has_defected,
                "mandate": mandate_str,
            }
            agent_records.append(rec)

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sim_id": self._sim_id,
            "round": round_num,
            "day": day,
            "time_of_day": time_of_day,
            "agents": agent_records,
            "summary": {
                "abandon_count": abandon_count,
                "defect_count": defect_count,
                "sentiment_distribution": sentiment_dist,
                "cross_agent_repeated_phrases": cross_agent_repeated[:300],
            },
            "metrics": {
                "brand_sentiment": round(metrics.brand_sentiment, 3),
                "purchase_intent": round(metrics.purchase_intent, 3),
                "churn_risk": round(metrics.churn_risk, 3),
                "adoption_rate": round(metrics.adoption_rate, 3),
                "stability": round(metrics.stability, 3),
                "trust": round(metrics.trust, 3),
            },
        }
        self._write(record)

    def log_event(self, event_type: str, data: dict[str, Any]):
        self._write({
            "ts": datetime.now(timezone.utc).isoformat(),
            "sim_id": self._sim_id,
            "event": event_type,
            "data": data,
        })

    def close(self):
        if self._fh:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None
