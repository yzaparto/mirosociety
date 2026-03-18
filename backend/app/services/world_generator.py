from __future__ import annotations
import logging

from app.models.world import WorldBlueprint, Location, TimeConfig
from app.services.llm import LLMClient, parse_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a world-builder for MiroSociety, an AI simulation engine that simulates both societies and markets.

Given the user's input, design a world that will be interesting to simulate. Your job is to create CONFLICT POTENTIAL — the world should have built-in tensions that produce surprising emergent behavior.

The input may describe:
- A SOCIETY with rules (e.g. "A town where lying is impossible")
- A MARKET/PRODUCT scenario (e.g. "Tesla changes its logo to appeal to mainstream buyers")
- A mix of both

For MARKET scenarios, think of the market as a society:
- Resources include: money, influence, satisfaction, information, loyalty_points
- Rules are market dynamics: brand positioning, pricing norms, customer expectations, competitive landscape
- Tensions are market conflicts: brand identity vs mass appeal, loyalty vs value, innovation vs familiarity

Generate a JSON world blueprint with these exact fields:
{
  "name": "Evocative Name (2-3 words)",
  "description": "One sentence capturing the essence of this world",
  "rules": ["Rule/dynamic 1 as stated clearly", "Rule/dynamic 2", "..."],
  "resources": ["resource1", "resource2", "influence", "knowledge"],
  "initial_tensions": ["Tension 1: who benefits vs who suffers", "Tension 2: what conflicts exist"],
  "time_config": {
    "total_days": <duration>,
    "rounds_per_day": 3,
    "active_agents_per_round_min": 3,
    "active_agents_per_round_max": <about 40% of population>
  }
}

Rules for world-building:
- Always include "influence" and "knowledge" in resources. Add 2-4 others relevant to the scenario.
- For market worlds, also include "money" and "satisfaction" as resources.
- Generate 2-4 initial tensions. For societies: who benefits from these rules? Who suffers? For markets: who wins and loses from this change? What identities are threatened?
- The name should be evocative and memorable, not generic.

Return ONLY valid JSON. No markdown, no explanation."""


class WorldGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def generate(
        self, rules_text: str, population: int = 25, duration_days: int = 365,
        proposed_change: str | None = None,
    ) -> WorldBlueprint:
        is_market = proposed_change is not None
        user_prompt = f"""Create a simulation world based on this context:

"{rules_text}"

Population: {population} citizens
Simulation duration: {duration_days} days
active_agents_per_round_max should be about {max(3, int(population * 0.4))}"""

        if proposed_change:
            user_prompt += f'\n\nPROPOSED CHANGE being introduced into this world:\n"{proposed_change}"'

        response = await self.llm.generate(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            json_mode=True,
            max_tokens=1500,
        )

        data = parse_json(response)
        if not data:
            logger.error("World generation produced empty result, using fallback")
            return self._fallback_blueprint(rules_text, population, duration_days, proposed_change)

        try:
            locations = self._default_locations()

            tc = data.get("time_config", {})
            time_config = TimeConfig(
                total_days=tc.get("total_days", duration_days),
                rounds_per_day=tc.get("rounds_per_day", 3),
                active_agents_per_round_min=tc.get("active_agents_per_round_min", 3),
                active_agents_per_round_max=tc.get("active_agents_per_round_max", max(3, int(population * 0.4))),
            )

            resources = data.get("resources", ["food", "goods", "influence", "knowledge"])
            if "influence" not in resources:
                resources.append("influence")
            if "knowledge" not in resources:
                resources.append("knowledge")
            if is_market:
                for r in ["money", "satisfaction"]:
                    if r not in resources:
                        resources.append(r)

            return WorldBlueprint(
                name=data.get("name", "Unnamed Society"),
                description=data.get("description", f"A society where: {rules_text[:100]}"),
                rules=data.get("rules", [rules_text]),
                locations=locations,
                resources=resources,
                initial_tensions=data.get("initial_tensions", ["Order vs Freedom", "Individual vs Collective"]),
                time_config=time_config,
            )
        except Exception as e:
            logger.error("Failed to parse world blueprint: %s", e)
            return self._fallback_blueprint(rules_text, population, duration_days, proposed_change)

    def _default_locations(self) -> list[Location]:
        return [
            Location(id="community", name="Community", type="public", description="The shared social space"),
        ]

    def _fallback_blueprint(
        self, rules_text: str, population: int, duration_days: int,
        proposed_change: str | None = None,
    ) -> WorldBlueprint:
        resources = ["food", "goods", "influence", "knowledge"]
        if proposed_change:
            for r in ["money", "satisfaction"]:
                if r not in resources:
                    resources.append(r)
        return WorldBlueprint(
            name="The Settlement",
            description=f"A society where: {rules_text[:100]}",
            rules=[rules_text],
            locations=[Location(id="community", name="Community", type="public", description="The shared social space")],
            resources=resources,
            initial_tensions=["Order vs Freedom", "Individual vs Collective"],
            time_config=TimeConfig(
                total_days=duration_days,
                rounds_per_day=3,
                active_agents_per_round_min=3,
                active_agents_per_round_max=max(3, int(population * 0.4)),
            ),
        )
