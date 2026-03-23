from __future__ import annotations
import logging
import random
from typing import Any

from app.models.world import WorldState, WorldMetrics
from app.models.agent import AgentPersona
from app.services.llm import LLMClient, parse_json

logger = logging.getLogger(__name__)

EVENT_SYSTEM_PROMPT = """You are the fate engine for {world_name}, a society simulation.
Rules of this world: {rules}

The society has become too stable and needs disruption to stay interesting.
Generate a minor but consequential environmental event that would shake things up.

Examples: resource scarcity, a mysterious stranger arrives, a natural disaster, a scandal is revealed, a neighboring community makes contact, an old secret surfaces, a disease breaks out, a valuable resource is discovered.

The event should:
- Be relevant to this specific society and its rules
- Affect multiple citizens differently (some benefit, some suffer)
- Create new tensions or reactivate old ones
- Be described in 1-2 vivid sentences

Return JSON:
{{
  "event": "Description of what happens",
  "resource_changes": {{"resource_name": change_amount}}
}}"""

EVENT_SYSTEM_PROMPT_MARKET = """You are the fate engine for {world_name}, a market simulation.
Market context: {rules}

The consumer conversation has stagnated — people are talking but not acting.
Generate a MARKET EVENT that forces consumers to make actual decisions (buy, leave, switch, recommend).

Good market events:
- A competitor launches a flash sale or exclusive offer
- A viral negative review goes mainstream
- A celebrity endorsement or public rejection
- A product recall or quality issue surfaces
- A price increase or decrease is announced
- A key feature breaks or a new feature launches
- An industry report ranks the brand lower than expected
- A class action lawsuit is filed

The event should:
- Directly impact purchase decisions, not just opinions
- Create urgency — consumers must decide NOW
- Affect different consumer segments differently
- Be described in 1-2 concrete sentences

Return JSON:
{{
  "event": "Description of what happens",
  "resource_changes": {{"resource_name": change_amount}}
}}"""

SPLINTER_SYSTEM_PROMPT = """You are a social dynamics engine for {world_name}.
The dominant faction "{faction_name}" has grown too large ({member_count}/{total} citizens).

In real societies, large factions always develop internal disagreements about methods, priorities, or leadership.

Generate a splinter ideology that:
- Agrees with the faction's core goal but disagrees on methods
- Would appeal to 2-3 members of the faction
- Creates a new point of tension within the group

Return JSON:
{{
  "splinter_belief": "The belief that differentiates the splinter group",
  "reason": "Why some members would break away"
}}"""


class TensionEngine:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._stable_rounds: dict[str, int] = {}
        self._quiet_rounds: dict[str, int] = {}

    def cleanup(self, sim_id: str) -> None:
        self._stable_rounds.pop(sim_id, None)
        self._quiet_rounds.pop(sim_id, None)

    @staticmethod
    def _snapshot_counterfactual(
        forecast: Any,
        sim_id: str,
        event_round: int,
        event_text: str,
    ) -> None:
        if forecast is None:
            return
        try:
            forecast.snapshot_for_counterfactual(sim_id, event_round, event_text)
        except Exception:
            pass

    @staticmethod
    def find_bridge_nodes(agents: list[AgentPersona]) -> list[int]:
        faction_map: dict[str, set[int]] = {}
        for a in agents:
            if a.faction:
                faction_map.setdefault(a.faction, set()).add(a.id)

        if len(faction_map) < 2:
            return []

        bridges: list[int] = []
        for agent in agents:
            connected_factions: set[str] = set()
            for edge in agent.social_connections:
                if edge.strength < 0.3:
                    continue
                for faction, members in faction_map.items():
                    if edge.target_id in members:
                        connected_factions.add(faction)
            if agent.faction:
                connected_factions.add(agent.faction)
            if len(connected_factions) >= 2:
                bridges.append(agent.id)
        return bridges

    async def check_and_apply(
        self,
        world_state: WorldState,
        agents: list[AgentPersona],
        recent_actions_significant: int,
        sim_id: str = "",
        forecast: Any | None = None,
    ) -> tuple[WorldState, list[AgentPersona], str | None]:
        is_market = self._is_market(world_state)

        stable = self._stable_rounds.get(sim_id, 0)
        quiet = self._quiet_rounds.get(sim_id, 0)

        is_stable = (
            world_state.metrics.stability > 0.85
            and world_state.metrics.conflict < 0.15
        )

        if is_stable:
            stable += 1
        else:
            stable = max(0, stable - 1)

        if recent_actions_significant == 0:
            quiet += 1
        else:
            quiet = 0

        self._stable_rounds[sim_id] = stable
        self._quiet_rounds[sim_id] = quiet

        market_stagnation = is_market and (
            (world_state.metrics.adoption_rate > 0.85 and stable >= 2)
            or (world_state.metrics.churn_risk > 0.85 and stable >= 2)
        )

        talk_only_stagnation = is_market and quiet >= 2

        quiet_threshold = 3 if is_market else 5
        base_needs_intervention = (
            stable >= 3
            or quiet >= quiet_threshold
            or market_stagnation
            or talk_only_stagnation
        )

        forecast_disrupt = False
        if forecast is not None and getattr(forecast, "available", False):
            try:
                forecast_disrupt = bool(forecast.should_disrupt(sim_id))
            except Exception:
                forecast_disrupt = False

        partial_quiet_met = quiet >= (2 if is_market else 4)
        partial_stable_met = stable >= 2
        forecast_accelerates = forecast_disrupt and (
            partial_quiet_met or partial_stable_met or market_stagnation or talk_only_stagnation
        )

        quiet_fallback = quiet > 12

        needs_intervention = base_needs_intervention or forecast_accelerates or quiet_fallback

        dominant_faction = self._find_dominant_faction(agents)

        if not needs_intervention and not dominant_faction:
            return world_state, agents, None

        if dominant_faction and random.random() < 0.4:
            agents, event_desc = await self._faction_fracture(
                world_state, agents, dominant_faction, forecast=forecast, sim_id=sim_id
            )
            self._stable_rounds[sim_id] = 0
            return world_state, agents, event_desc
        elif talk_only_stagnation:
            agents, event_desc = self._internal_pressure(
                agents, world_state=world_state, forecast=forecast, sim_id=sim_id
            )
            self._stable_rounds[sim_id] = 0
            self._quiet_rounds[sim_id] = 0
            return world_state, agents, event_desc
        elif quiet >= quiet_threshold or random.random() < 0.5:
            world_state, agents, event_desc = await self._external_event(
                world_state, agents, forecast=forecast, sim_id=sim_id
            )
            self._stable_rounds[sim_id] = 0
            self._quiet_rounds[sim_id] = 0
            return world_state, agents, event_desc
        else:
            agents, event_desc = self._internal_pressure(
                agents, world_state=world_state, forecast=forecast, sim_id=sim_id
            )
            self._stable_rounds[sim_id] = 0
            return world_state, agents, event_desc

    def _find_dominant_faction(self, agents: list[AgentPersona]) -> str | None:
        faction_counts: dict[str, int] = {}
        for a in agents:
            if a.faction:
                faction_counts[a.faction] = faction_counts.get(a.faction, 0) + 1

        total = len(agents)
        for faction, count in faction_counts.items():
            if count / total > 0.6:
                return faction
        return None

    def _internal_pressure(
        self,
        agents: list[AgentPersona],
        world_state: WorldState,
        forecast: Any | None = None,
        sim_id: str = "",
    ) -> tuple[list[AgentPersona], str]:
        day = world_state.day
        calm_agents = [
            a for a in agents
            if a.emotional_state in ("calm", "content", "satisfied", "curious")
        ]
        if not calm_agents:
            calm_agents = agents

        targets = random.sample(calm_agents, min(3, len(calm_agents)))

        is_market = (
            world_state.metrics.adoption_rate > 0.0
            or world_state.metrics.churn_risk != 0.2
            or world_state.metrics.brand_sentiment != 0.5
        )

        if is_market:
            grievances = [
                "Am I just following the crowd with this purchase?",
                "I'm not sure this brand represents me anymore",
                "The competitors are starting to look more appealing",
                "I feel like I'm paying a premium for nothing",
                "Everyone's talking about this change but nobody actually likes it",
                "I was loyal to this brand and they betrayed that trust",
            ]

            action_nudges = [
                "I should seriously consider switching to a competitor",
                "I need to compare alternatives before I commit further",
                "I'm going to recommend people avoid this brand until things improve",
                "I think it's time to cancel my subscription / sell my product",
                "I've been on the fence long enough — time to decide whether I'm in or out",
                "I should publicly share my honest review of this brand",
            ]
        else:
            grievances = [
                "I've been overlooked while others prosper",
                "The system benefits others more than me",
                "I'm tired of following rules that don't serve me",
                "Something needs to change around here",
                "I deserve better than this",
                "The current order is unfair to people like me",
            ]
            action_nudges = []

        names = ", ".join(t.name for t in targets)
        if is_market:
            event_desc = (
                f"Consumer patience wore thin: {names} started seriously reconsidering their choices."
            )
        else:
            event_desc = (
                f"A quiet restlessness stirred among some citizens: {names} began to question things."
            )
        self._snapshot_counterfactual(forecast, sim_id, day, event_desc)

        for agent in targets:
            agent.emotional_state = random.choice(["restless", "dissatisfied", "frustrated"])
            if is_market:
                nudge = random.uniform(0.05, 0.12)
                if agent.personality.brand_loyalty > 0.3:
                    agent.personality.brand_loyalty = max(0.0, agent.personality.brand_loyalty - nudge)
                if agent.personality.price_sensitivity < 0.9:
                    agent.personality.price_sensitivity = min(1.0, agent.personality.price_sensitivity + nudge * 0.7)
            new_belief = random.choice(grievances)
            if new_belief not in agent.beliefs:
                agent.beliefs.append(new_belief)
            if is_market and action_nudges:
                action_belief = random.choice(action_nudges)
                if action_belief not in agent.beliefs:
                    agent.beliefs.append(action_belief)
                    if len(agent.beliefs) > 10:
                        agent.beliefs.pop(0)
                agent.working_memory.append(
                    f"Day {day}: I'm done just talking about this — I need to make a decision."
                )
            else:
                agent.working_memory.append(
                    f"Day {day}: A growing sense of unease settled over me."
                )

        return agents, event_desc

    @staticmethod
    def _is_market(world_state: WorldState) -> bool:
        return (
            world_state.metrics.adoption_rate > 0.0
            or world_state.metrics.churn_risk != 0.2
            or world_state.metrics.brand_sentiment != 0.5
        )

    async def _external_event(
        self,
        world_state: WorldState,
        agents: list[AgentPersona],
        forecast: Any | None = None,
        sim_id: str = "",
    ) -> tuple[WorldState, list[AgentPersona], str]:
        is_market = self._is_market(world_state)

        if is_market:
            system = EVENT_SYSTEM_PROMPT_MARKET.format(
                world_name=world_state.blueprint.name,
                rules="; ".join(world_state.blueprint.rules),
            )
        else:
            system = EVENT_SYSTEM_PROMPT.format(
                world_name=world_state.blueprint.name,
                rules="; ".join(world_state.blueprint.rules),
            )

        user = (
            f"Current state: stability={world_state.metrics.stability:.2f}, "
            f"conflict={world_state.metrics.conflict:.2f}, "
            f"brand_sentiment={world_state.metrics.brand_sentiment:.2f}, "
            f"churn_risk={world_state.metrics.churn_risk:.2f}, "
            f"adoption_rate={world_state.metrics.adoption_rate:.2f}, "
            f"day={world_state.day}, "
            f"institutions={[i.name for i in world_state.institutions]}, "
            f"disputes={world_state.active_disputes}"
        )

        response = await self.llm.generate(system=system, user=user, json_mode=True, max_tokens=300)
        data = parse_json(response)

        event_desc = data.get("event", "An unexpected disruption shook the community.")

        self._snapshot_counterfactual(forecast, sim_id, world_state.day, event_desc)

        resource_changes = data.get("resource_changes", {})
        if resource_changes:
            world_state.active_disputes.append(f"Disruption: {event_desc[:80]}")

        world_state.metrics.stability = max(0.0, world_state.metrics.stability - 0.15)
        world_state.metrics.conflict = min(1.0, world_state.metrics.conflict + 0.1)

        if is_market:
            world_state.metrics.churn_risk = min(1.0, world_state.metrics.churn_risk + 0.08)
            world_state.metrics.brand_sentiment = max(0.0, world_state.metrics.brand_sentiment - 0.05)

        initial_count = max(3, len(agents) // 3)
        affected = random.sample(agents, min(initial_count, len(agents)))
        for agent in affected:
            event_belief = f"After the recent event: {event_desc[:60]} — things are changing"
            if event_belief not in agent.beliefs:
                agent.beliefs.append(event_belief)
                if len(agent.beliefs) > 10:
                    agent.beliefs.pop(0)

        self._event_initial_recipients = [a.id for a in affected]

        return world_state, agents, event_desc

    def get_event_recipients(self) -> list[int] | None:
        recipients = getattr(self, "_event_initial_recipients", None)
        self._event_initial_recipients = None
        return recipients

    async def _faction_fracture(
        self,
        world_state: WorldState,
        agents: list[AgentPersona],
        faction_name: str,
        forecast: Any | None = None,
        sim_id: str = "",
    ) -> tuple[list[AgentPersona], str]:
        members = [a for a in agents if a.faction == faction_name]

        system = SPLINTER_SYSTEM_PROMPT.format(
            world_name=world_state.blueprint.name,
            faction_name=faction_name,
            member_count=len(members),
            total=len(agents),
        )
        response = await self.llm.generate(system=system, user="Generate a splinter ideology.", json_mode=True, max_tokens=200)
        data = parse_json(response)

        splinter_belief = data.get("splinter_belief", f"The {faction_name} has lost its way")

        splinter_targets = random.sample(members, min(3, len(members)))
        names = ", ".join(t.name for t in splinter_targets)
        event_desc = (
            f"Cracks appeared in {faction_name}. {names} began privately questioning "
            f"the group's direction: \"{splinter_belief}\""
        )
        self._snapshot_counterfactual(forecast, sim_id, world_state.day, event_desc)

        for agent in splinter_targets:
            if splinter_belief not in agent.beliefs:
                agent.beliefs.append(splinter_belief)
            agent.emotional_state = "conflicted"
            agent.working_memory.append(
                f"I've started questioning whether {faction_name} is truly on the right path."
            )

        return agents, event_desc
