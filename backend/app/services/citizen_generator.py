from __future__ import annotations
import logging
from typing import Callable, Awaitable

from app.models.agent import AgentPersona, Personality
from app.models.world import WorldBlueprint
from app.services.llm import LLMClient, parse_json

logger = logging.getLogger(__name__)

CAST_SYSTEM_PROMPT = """You are a character designer for MiroSociety, an AI society simulation.

Given a world blueprint, design a diverse cast of citizens. Each citizen should be a distinct, memorable character with a clear role in the society and a specific stance on the society's rules and tensions.

CRITICAL: Citizens must have DIVERSE stances on the society's rules.
For each initial tension, generate citizens across the spectrum:
- True believers who love the rules
- Pragmatists who comply but have reservations
- Quiet dissenters who obey but resent it
- Active resisters who will test boundaries
- Exploiters who find loopholes
- The indifferent who just want to be left alone

A town of reasonable moderates is boring. A town with extremists, idealists, cynics, and opportunists produces stories.

Return a JSON array of citizen summaries:
[
  {
    "name": "Full Name",
    "role": "Occupation/Role",
    "age": 34,
    "personality_hook": "One sentence that captures who this person is",
    "stance": "Their position on the society's key tensions"
  }
]

Requirements:
- Age range from 18 to 75
- Mix of genders (don't state gender explicitly, let names imply it naturally)
- At least 2 citizens per tension stance (for, against, indifferent, exploiter)
- Each name should be distinct and memorable
- Roles should create natural interaction patterns (trade, governance, education, labor, etc.)

Return ONLY valid JSON array. No markdown, no explanation.

For MARKET/PRODUCT scenarios, citizens are consumer personas:
- Brand loyalists who see ownership as identity
- First-time buyers comparing options
- Tech enthusiasts excited by innovation
- Luxury buyers wanting premium signals
- Skeptics who distrust the brand
- Casual observers vaguely aware of the product
- Influencers who shape opinion
- Competitors' loyal customers

Roles for market worlds are things like:
- "Tesla Model 3 owner since 2022"
- "Automotive journalist covering EVs"
- "Former BMW owner considering an EV"
- "Reddit power user, r/teslamotors moderator"
- "Rivian reservation holder"
"""

PERSONA_SYSTEM_PROMPT = """You are a character psychologist for MiroSociety, an AI society simulation.

Given a citizen summary and world context, generate a full psychological profile.

Return JSON with these exact fields:
{
  "background": "2-3 sentence backstory that explains who they are and why",
  "personality": {
    "honesty": 0.0-1.0,
    "ambition": 0.0-1.0,
    "empathy": 0.0-1.0,
    "confrontational": 0.0-1.0,
    "conformity": 0.0-1.0,
    "brand_loyalty": 0.0-1.0,
    "price_sensitivity": 0.0-1.0,
    "social_proof": 0.0-1.0,
    "novelty_seeking": 0.0-1.0
  },
  "goals": ["Goal 1", "Goal 2", "Goal 3"],
  "beliefs": ["Belief about the rules", "Belief about society", "Personal belief"],
  "resources": {"resource_name": amount_0_to_100}
}

Personality scores:
- honesty: 1.0 = always truthful, 0.0 = habitual deceiver
- ambition: 1.0 = relentlessly driven, 0.0 = content with status quo
- empathy: 1.0 = deeply feels others' pain, 0.0 = coldly indifferent
- confrontational: 1.0 = seeks conflict, 0.0 = avoids all confrontation
- conformity: 1.0 = follows all rules without question, 0.0 = rebels against any authority

Market personality scores:
- brand_loyalty: 1.0 = ride-or-die fan, 0.0 = switches at a whim
- price_sensitivity: 1.0 = every penny matters, 0.0 = money is no object
- social_proof: 1.0 = does what everyone else does, 0.0 = proudly contrarian
- novelty_seeking: 1.0 = first in line for anything new, 0.0 = hates change

Make the personality internally consistent with the character's role, age, and stance.
Goals should be specific to this character, not generic.
Beliefs should reflect their stance on the society's rules.
Resources should reflect their social position (a merchant has more goods, a scholar has more knowledge).

Return ONLY valid JSON. No markdown, no explanation."""

RELATIONSHIPS_SYSTEM_PROMPT = """You are a social network designer for MiroSociety, an AI society simulation.

Given a list of citizens in a society, generate initial relationships between them.

Return a JSON array:
[
  {
    "agent_id": 0,
    "relationships": {
      "3": "Description of relationship with agent 3",
      "7": "Description of relationship with agent 7"
    }
  }
]

Rules:
- Every citizen should have 2-4 initial relationships
- Mix of positive (friend, ally, family, mentor) and negative (rival, distrusts, resents)
- Include at least some family ties and professional connections
- Relationships should create interesting dynamics (allies on opposite sides of a tension, rivals who need each other, etc.)
- Use agent IDs as string keys in the relationships dict
- Keep descriptions to one concise sentence

Return ONLY valid JSON array. No markdown, no explanation."""


class CitizenGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def generate(
        self,
        blueprint: WorldBlueprint,
        count: int = 25,
        on_citizen: Callable[[AgentPersona], Awaitable[None]] | None = None,
        proposed_change: str | None = None,
        segments: list[dict] | None = None,
    ) -> list[AgentPersona]:
        cast = await self._generate_cast(blueprint, count, proposed_change, segments)
        agents = await self._generate_personas(blueprint, cast, on_citizen)
        agents = await self._generate_relationships(blueprint, agents)
        return agents

    async def _generate_cast(
        self,
        blueprint: WorldBlueprint,
        count: int,
        proposed_change: str | None = None,
        segments: list[dict] | None = None,
    ) -> list[dict]:
        world_context = (
            f"World: {blueprint.name}\n"
            f"Description: {blueprint.description}\n"
            f"Rules: {'; '.join(blueprint.rules)}\n"
            f"Resources: {', '.join(blueprint.resources)}\n"
            f"Tensions: {'; '.join(blueprint.initial_tensions)}"
        )

        user_text = f"{world_context}\n\nGenerate exactly {count} citizens."
        if proposed_change:
            user_text += f'\n\nPROPOSED CHANGE: "{proposed_change}"'
        if segments:
            seg_text = "\n".join(
                f"- {s['name']}: {s['description']}" + (f" (count: {s['count']})" if s.get('count') else "")
                for s in segments
            )
            user_text += f"\n\nTARGET SEGMENTS (distribute citizens across these):\n{seg_text}"

        response = await self.llm.generate(
            system=CAST_SYSTEM_PROMPT,
            user=user_text,
            json_mode=True,
            max_tokens=3000,
        )

        data = parse_json(response)
        if isinstance(data, dict) and "citizens" in data:
            cast = data["citizens"]
        elif isinstance(data, list):
            cast = data
        else:
            cast = []

        if len(cast) < count:
            logger.warning("Cast generation returned %d/%d citizens, padding", len(cast), count)
            while len(cast) < count:
                idx = len(cast)
                cast.append({
                    "name": f"Citizen {idx + 1}",
                    "role": "Laborer",
                    "age": 30 + (idx % 40),
                    "personality_hook": "A quiet person trying to get by",
                    "stance": "Indifferent to the rules",
                })

        return cast[:count]

    async def _generate_personas(
        self,
        blueprint: WorldBlueprint,
        cast: list[dict],
        on_citizen: Callable[[AgentPersona], Awaitable[None]] | None = None,
    ) -> list[AgentPersona]:
        agents: list[AgentPersona] = []

        batch_size = 5
        for batch_start in range(0, len(cast), batch_size):
            batch = cast[batch_start:batch_start + batch_size]
            prompts = []
            for member in batch:
                world_ctx = (
                    f"World: {blueprint.name}\n"
                    f"Rules: {'; '.join(blueprint.rules)}\n"
                    f"Resources: {', '.join(blueprint.resources)}\n"
                    f"Tensions: {'; '.join(blueprint.initial_tensions)}"
                )
                citizen_ctx = (
                    f"Name: {member['name']}\n"
                    f"Role: {member['role']}\n"
                    f"Age: {member['age']}\n"
                    f"Personality hook: {member.get('personality_hook', '')}\n"
                    f"Stance on tensions: {member.get('stance', 'unknown')}"
                )
                prompts.append((PERSONA_SYSTEM_PROMPT, f"{world_ctx}\n\n{citizen_ctx}"))

            responses = await self.llm.generate_batch(prompts, json_mode=True, max_tokens=800)

            for i, response in enumerate(responses):
                idx = batch_start + i
                member = cast[idx]
                data = parse_json(response)

                personality_data = data.get("personality", {})
                personality = Personality(
                    honesty=self._clamp(personality_data.get("honesty", 0.5)),
                    ambition=self._clamp(personality_data.get("ambition", 0.5)),
                    empathy=self._clamp(personality_data.get("empathy", 0.5)),
                    confrontational=self._clamp(personality_data.get("confrontational", 0.5)),
                    conformity=self._clamp(personality_data.get("conformity", 0.5)),
                    brand_loyalty=self._clamp(personality_data.get("brand_loyalty", 0.5)),
                    price_sensitivity=self._clamp(personality_data.get("price_sensitivity", 0.5)),
                    social_proof=self._clamp(personality_data.get("social_proof", 0.5)),
                    novelty_seeking=self._clamp(personality_data.get("novelty_seeking", 0.5)),
                )

                resources = data.get("resources", {})
                for res in blueprint.resources:
                    if res not in resources:
                        resources[res] = 50

                agent = AgentPersona(
                    id=idx,
                    name=member["name"],
                    role=member["role"],
                    age=member.get("age", 30),
                    personality=personality,
                    background=data.get("background", member.get("personality_hook", "")),
                    goals=data.get("goals", ["Survive", "Find purpose"]),
                    core_memory=[],
                    working_memory=[],
                    beliefs=data.get("beliefs", []),
                    relationships={},
                    resources={k: int(v) if isinstance(v, (int, float)) else 50 for k, v in resources.items()},
                    location="community",
                    faction=None,
                    emotional_state="curious",
                )

                agents.append(agent)
                if on_citizen:
                    await on_citizen(agent)

        return agents

    async def _generate_relationships(
        self, blueprint: WorldBlueprint, agents: list[AgentPersona]
    ) -> list[AgentPersona]:
        agent_summaries = "\n".join(
            f"Agent {a.id}: {a.name}, {a.role}, age {a.age}. {a.background[:100]}"
            for a in agents
        )

        response = await self.llm.generate(
            system=RELATIONSHIPS_SYSTEM_PROMPT,
            user=f"World: {blueprint.name}\nRules: {'; '.join(blueprint.rules)}\n\nCitizens:\n{agent_summaries}",
            json_mode=True,
            max_tokens=3000,
        )

        data = parse_json(response)
        if isinstance(data, dict) and "relationships" in data:
            rel_list = data["relationships"]
        elif isinstance(data, list):
            rel_list = data
        else:
            rel_list = []

        agent_map = {a.id: a for a in agents}
        for entry in rel_list:
            aid = entry.get("agent_id")
            if aid is not None and aid in agent_map:
                rels = entry.get("relationships", {})
                agent_map[aid].relationships = {str(k): str(v) for k, v in rels.items()}

        return list(agent_map.values())

    @staticmethod
    def _clamp(v, lo=0.0, hi=1.0) -> float:
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return 0.5
