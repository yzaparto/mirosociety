from __future__ import annotations

import logging
import random

from app.models.agent import AgentPersona, LifePressure
from app.models.world import WorldState
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)

EVAL_INTERVAL = 6
MAX_EVENTS_PER_CYCLE = 2
MAX_PRESSURES = 4
POSITIVE_RATIO = 0.35

CATALOG: dict[str, dict[str, list[dict]]] = {
    "finances": {
        "negative": [
            {"template": "unexpected_expense", "description": "A major unexpected expense hits", "domain_delta": -0.2, "pressure": "Must cover urgent costs", "weight_factors": {"finances": "inverse"}},
            {"template": "debt_called_in", "description": "An old debt comes due", "domain_delta": -0.15, "pressure": "Creditor demands repayment", "weight_factors": {"finances": "inverse"}},
            {"template": "theft_or_loss", "description": "Resources stolen or lost", "domain_delta": -0.25, "pressure": "Lost significant resources", "weight_factors": {}},
        ],
        "positive": [
            {"template": "windfall", "description": "An unexpected financial gain", "domain_delta": 0.2, "pressure": None, "weight_factors": {"career": "direct"}},
            {"template": "good_trade", "description": "A lucrative opportunity", "domain_delta": 0.1, "pressure": None, "weight_factors": {"ambition": "direct"}},
        ],
    },
    "career": {
        "negative": [
            {"template": "job_threat", "description": "Position is at risk", "domain_delta": -0.2, "pressure": "Must prove your worth or lose your role", "weight_factors": {"career": "inverse", "conformity": "inverse"}},
            {"template": "public_failure", "description": "A public professional humiliation", "domain_delta": -0.3, "pressure": "Reputation damaged", "weight_factors": {"ambition": "direct"}},
        ],
        "positive": [
            {"template": "promotion", "description": "Recognition and advancement", "domain_delta": 0.25, "pressure": None, "weight_factors": {"ambition": "direct", "career": "direct"}},
            {"template": "new_skill", "description": "Mastered something valuable", "domain_delta": 0.1, "pressure": None, "weight_factors": {}},
        ],
    },
    "health": {
        "negative": [
            {"template": "illness", "description": "A health setback", "domain_delta": -0.2, "pressure": "Need rest and care", "weight_factors": {"health": "inverse"}},
            {"template": "injury", "description": "Physical injury limits activity", "domain_delta": -0.15, "pressure": "Recovery needed", "weight_factors": {}},
        ],
        "positive": [
            {"template": "recovery", "description": "Health improves significantly", "domain_delta": 0.2, "pressure": None, "weight_factors": {"health": "inverse"}},
            {"template": "vitality", "description": "A period of exceptional energy", "domain_delta": 0.1, "pressure": None, "weight_factors": {"health": "direct"}},
        ],
    },
    "family": {
        "negative": [
            {"template": "family_illness", "description": "A family member falls ill", "domain_delta": None, "pressure": "{family_member} is sick", "weight_factors": {}},
            {"template": "family_conflict", "description": "A serious disagreement with family", "domain_delta": None, "pressure": "Tension with {family_member}", "weight_factors": {"confrontational": "direct"}},
            {"template": "dependent_need", "description": "A dependent needs something urgent", "domain_delta": None, "pressure": "{family_member} needs help urgently", "weight_factors": {}},
        ],
        "positive": [
            {"template": "family_milestone", "description": "A family celebration", "domain_delta": None, "pressure": None, "weight_factors": {}},
            {"template": "reconciliation", "description": "A strained relationship heals", "domain_delta": None, "pressure": None, "weight_factors": {"empathy": "direct"}},
        ],
    },
}

CASCADE_RULES: dict[str, list[dict]] = {
    "job_threat": [
        {"condition": lambda a: a.life_state.finances < 0.4, "domain": "finances", "delta": -0.1, "pressure_desc": "Without steady work, money is running out fast"},
    ],
    "family_illness": [
        {"condition": lambda a: any(f.dependency > 0.5 for f in a.life_state.family), "domain": "finances", "delta": -0.05, "pressure_desc": "Medical costs adding up"},
        {"condition": lambda a: a.personality.empathy > 0.6, "domain": "health", "delta": -0.1, "pressure_desc": "Stress of caregiving wearing you down"},
    ],
    "unexpected_expense": [
        {"condition": lambda a: a.life_state.finances < 0.3, "domain": "career", "delta": 0.0, "pressure_desc": "Desperate for income"},
    ],
}

LIFE_DOMAINS = ["finances", "career", "health"]


class LifeEngine:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def evaluate(
        self,
        agents: list[AgentPersona],
        world_state: WorldState,
        round_num: int,
    ) -> list[tuple[AgentPersona, str]]:
        if round_num % EVAL_INTERVAL != 0:
            return []

        current_day = world_state.day
        results: list[tuple[AgentPersona, str]] = []

        eligible = [a for a in agents if a.life_state is not None]
        for agent in eligible:
            self._tick_pressures(agent, current_day)

        candidates = self._select_candidates(eligible)

        fired = 0
        for agent in candidates:
            if fired >= MAX_EVENTS_PER_CYCLE:
                break
            event = self._select_event(agent)
            if event is None:
                continue
            description = await self._personalize_event(agent, event)
            self._apply_event(agent, event, current_day)
            results.append((agent, description))
            fired += 1

        return results

    def _tick_pressures(self, agent: AgentPersona, current_day: int) -> None:
        ls = agent.life_state
        if ls is None:
            return
        surviving: list[LifePressure] = []
        for p in ls.pressures:
            if p.deadline_day is not None and current_day > p.deadline_day:
                p.severity = min(1.0, p.severity + 0.2)
                p.deadline_day = None
                surviving.append(p)
                continue

            domain_val = getattr(ls, p.domain, None)
            if domain_val is not None and domain_val > 0.7 and p.severity < 0.4:
                ls.life_log.append(f"Resolved pressure: {p.description}")
                continue

            age = current_day - p.created_day
            if age > 20 and p.severity < 0.3:
                continue

            surviving.append(p)
        ls.pressures = surviving

    def _select_candidates(self, agents: list[AgentPersona]) -> list[AgentPersona]:
        scored: list[tuple[float, AgentPersona]] = []
        for agent in agents:
            ls = agent.life_state
            if ls is None:
                continue
            recency_score = 1.0 / (1.0 + len(ls.life_log))
            extremes = 0.0
            for domain in LIFE_DOMAINS:
                val = getattr(ls, domain, 0.5)
                extremes += abs(val - 0.5)
            noise = random.random() * 0.3
            score = recency_score + extremes + noise
            scored.append((score, agent))
        scored.sort(key=lambda x: x[0], reverse=True)
        pool = [a for _, a in scored]
        subset_size = max(1, len(pool) // 2)
        subset = pool[:subset_size]
        random.shuffle(subset)
        return subset

    def _select_event(self, agent: AgentPersona) -> dict | None:
        ls = agent.life_state
        if ls is None:
            return None

        is_positive = random.random() < POSITIVE_RATIO
        polarity = "positive" if is_positive else "negative"

        weighted_events: list[tuple[float, dict, str]] = []
        for domain, buckets in CATALOG.items():
            events = buckets.get(polarity, [])
            for evt in events:
                weight = 1.0
                for factor_name, direction in evt["weight_factors"].items():
                    if factor_name in LIFE_DOMAINS:
                        val = getattr(ls, factor_name, 0.5)
                    else:
                        val = getattr(agent.personality, factor_name, 0.5)

                    if direction == "inverse":
                        weight *= (1.0 - val + 0.1)
                    else:
                        weight *= (val + 0.1)
                weighted_events.append((weight, evt, domain))

        if not weighted_events:
            return None

        weights = [w for w, _, _ in weighted_events]
        chosen_weight, chosen_evt, chosen_domain = random.choices(
            weighted_events, weights=weights, k=1
        )[0]

        result = dict(chosen_evt)
        result["_domain"] = chosen_domain
        result["_polarity"] = polarity

        if chosen_domain == "family" and ls.family:
            member = random.choice(ls.family)
            if result.get("pressure") and "{family_member}" in result["pressure"]:
                result["pressure"] = result["pressure"].replace("{family_member}", member.name)
            result["_family_member"] = member.name

        return result

    async def _personalize_event(self, agent: AgentPersona, event_template: dict) -> str:
        ls = agent.life_state
        family_context = ""
        if ls and ls.family:
            names = [f"{m.name} ({m.relation})" for m in ls.family[:4]]
            family_context = f"Family: {', '.join(names)}. "

        member_name = event_template.get("_family_member", "")
        member_ref = f" involving {member_name}" if member_name else ""

        system = (
            "You narrate personal life events for a simulation character. "
            "Write a 1-2 sentence vivid description. Use the character's name and "
            "family member names when relevant. No meta-commentary."
        )
        user = (
            f"Character: {agent.name}, age {agent.age}, role: {agent.role}. "
            f"{family_context}"
            f"Event: {event_template['description']}{member_ref}. "
            f"Domain: {event_template['_domain']}. "
            f"Make it personal and specific."
        )
        try:
            return await self.llm.generate(system, user, max_tokens=120)
        except Exception:
            logger.warning("LLM personalization failed for %s, using template", agent.name)
            return event_template["description"]

    def _apply_event(self, agent: AgentPersona, event: dict, current_day: int) -> None:
        ls = agent.life_state
        if ls is None:
            return

        domain = event["_domain"]
        delta = event.get("domain_delta")
        if delta is not None and domain in LIFE_DOMAINS:
            current = getattr(ls, domain)
            new_val = max(0.0, min(1.0, current + delta))
            setattr(ls, domain, new_val)

        pressure_desc = event.get("pressure")
        if pressure_desc and len(ls.pressures) < MAX_PRESSURES:
            ls.pressures.append(LifePressure(
                domain=domain,
                description=pressure_desc,
                severity=abs(delta) if delta else 0.5,
                deadline_day=current_day + 10,
                created_day=current_day,
            ))

        ls.life_log.append(f"Day {current_day}: {event['description']}")
        self._apply_cascades(agent, event["template"], current_day)

    def _apply_cascades(self, agent: AgentPersona, template_name: str, current_day: int) -> None:
        ls = agent.life_state
        if ls is None:
            return

        rules = CASCADE_RULES.get(template_name, [])
        for rule in rules:
            try:
                if not rule["condition"](agent):
                    continue
            except Exception:
                continue

            cascade_domain = rule["domain"]
            cascade_delta = rule["delta"]
            if cascade_domain in LIFE_DOMAINS and cascade_delta != 0:
                current = getattr(ls, cascade_domain)
                new_val = max(0.0, min(1.0, current + cascade_delta))
                setattr(ls, cascade_domain, new_val)

            if rule.get("pressure_desc") and len(ls.pressures) < MAX_PRESSURES:
                ls.pressures.append(LifePressure(
                    domain=cascade_domain,
                    description=rule["pressure_desc"],
                    severity=0.4,
                    created_day=current_day,
                ))
