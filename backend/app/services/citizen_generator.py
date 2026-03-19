from __future__ import annotations
import logging
import random
from typing import Callable, Awaitable

from app.models.agent import (
    AgentPersona, Personality, SocialEdge, COMMUNICATION_STYLES,
    LifeState, FamilyMember, FormativeEvent, LifePressure,
)
from app.models.demographics import DemographicProfile
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
    "stance": "Their position on the society's key tensions",
    "communication_style": "one of: terse, sarcastic, verbose, question-asker, anecdote-teller, data-driven, emotional, passive-aggressive"
  }
]

CRITICAL: Assign DIVERSE communication styles across the cast. Do NOT make everyone 'emotional' or 'verbose'. A realistic group has:
- 1-2 terse people who barely speak
- 1-2 sarcastic people who use irony
- 1-2 who ask questions instead of making statements
- 1-2 who tell personal stories/anecdotes
- 1-2 data-driven people who cite facts
- The rest can be emotional, verbose, or passive-aggressive

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

DEMOGRAPHIC_CAST_PROMPT = """You are a character designer for MiroSociety, an AI society simulation.

You are generating citizens for a simulation set in a REAL CITY. Use the demographic data below to create a cast that PROPORTIONALLY mirrors the city's actual population.

CITY DEMOGRAPHICS:
- City: {city_name}, {state}
- Population: {population:,}
- Median household income: ${median_income:,}
- Poverty rate: {poverty_rate:.1f}%
- Unemployment rate: {unemployment_rate:.1f}%
- Median age: {median_age:.1f}

AGE DISTRIBUTION:
{age_dist}

OCCUPATION BREAKDOWN:
{occ_dist}

ETHNIC COMPOSITION:
{eth_dist}

{city_character}

INSTRUCTIONS:
- Match the age distribution proportionally. If 30% of the city is 25-34, roughly 30% of citizens should be in that range.
- Match the ethnic composition proportionally using culturally appropriate names.
- Match the occupation breakdown — if 40% are management/business, assign ~40% of citizens to white-collar roles.
- Income levels should reflect the median income and poverty rate — include both struggling and comfortable citizens.
- Each citizen still needs a distinct personality, a clear stance on the society's tensions, and a memorable hook.

Return a JSON array of citizen summaries:
[
  {{
    "name": "Full Name",
    "role": "Occupation/Role",
    "age": 34,
    "personality_hook": "One sentence that captures who this person is",
    "stance": "Their position on the society's key tensions",
    "communication_style": "one of: terse, sarcastic, verbose, question-asker, anecdote-teller, data-driven, emotional, passive-aggressive"
  }}
]

CRITICAL: Assign DIVERSE communication styles across the cast.
CRITICAL: Citizens must have DIVERSE stances on the society's rules — true believers, pragmatists, quiet dissenters, active resisters, exploiters, and the indifferent.

Return ONLY valid JSON array. No markdown, no explanation."""

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

LIFE_HISTORY_PROMPT = """You are a backstory writer for MiroSociety, an AI society simulation.

Given a citizen's persona, generate a detailed life history that explains WHY they are who they are.

Return JSON with these exact fields:
{{
  "childhood_summary": "4-5 sentences describing their childhood and upbringing. This should EXPLAIN their personality — a conformist was raised in a strict household, a rebel saw injustice early. The childhood must feel like the origin story for the adult.",
  "formative_events": [
    {{
      "age_at_event": 12,
      "description": "A vivid scene, not a summary. 'At twelve, she watched her father lose the family store to a tax collector who smirked the whole time.' NOT 'Had a difficult childhood.'",
      "lasting_effect": "A specific behavioral pattern: 'Never trusts anyone who smiles while delivering bad news'",
      "trait_modifier": {{"conformity": -0.1, "empathy": 0.15}}
    }}
  ],
  "family": [
    {{
      "name": "Full Name",
      "relation": "spouse|child|parent|sibling",
      "age": 34,
      "status": "healthy|ill|estranged|deceased",
      "dependency": 0.0,
      "bond_strength": 0.7
    }}
  ],
  "finances": 0.5,
  "career": 0.5,
  "health": 0.8,
  "initial_pressures": [
    {{
      "domain": "finances|health|career|family",
      "description": "Specific, personal, 2 sentences. NOT 'has money problems'. YES 'The roof collapsed last month and the repair quote is more than she earns in three months. Winter is two weeks away.'",
      "severity": 0.6
    }}
  ]
}}

CRITICAL RULES:
- Childhood MUST explain personality. High conformity? Strict parents. Low empathy? Learned to shut down emotions early. High ambition? Saw poverty and vowed to escape it.
- Formative events are SCENES, not summaries. Include sensory detail, a specific moment, a turning point.
- Generate exactly {num_events} formative events, spread across the character's life from childhood to recent years.
- trait_modifier values should be between -0.2 and +0.2. Use personality trait names: honesty, ambition, empathy, confrontational, conformity.
- Family should be age-appropriate: a 22-year-old has parents and maybe siblings, not adult children. A 60-year-old may have grandchildren. Some people are estranged or have deceased family.
- finances/career/health are floats 0.0-1.0 reflecting CURRENT status. Match to the character's role and age.
- NOT everyone is struggling. A merchant should have decent finances. A young laborer might be healthy but poor. An elder might be wealthy but in declining health.
- initial_pressures: 0-3 active life pressures. Some people have NO pressures — they're doing fine. Mix it up.
- DIVERSITY: Include a range of financial situations (some thriving, some struggling), health levels, family structures (single, married, widowed, estranged), and pressure counts.

Return ONLY valid JSON. No markdown, no explanation."""


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
        demographics: DemographicProfile | None = None,
    ) -> list[AgentPersona]:
        cast = await self._generate_cast(blueprint, count, proposed_change, segments, demographics)
        agents = await self._generate_personas(blueprint, cast, on_citizen)
        await self._generate_life_histories(blueprint, agents)
        self._apply_all_trait_modifiers(agents)
        self._enforce_life_diversity(agents)
        agents = await self._generate_relationships(blueprint, agents)
        if proposed_change:
            self._assign_knowledge_levels(agents)
        return agents

    async def generate_fast(
        self,
        blueprint: WorldBlueprint,
        count: int = 25,
        on_citizen: Callable[[AgentPersona], Awaitable[None]] | None = None,
        proposed_change: str | None = None,
        segments: list[dict] | None = None,
        demographics: DemographicProfile | None = None,
    ) -> list[AgentPersona]:
        """Phase 1: generate cast + personas only. Returns agents that are
        functional but lack life histories and relationships. This is enough
        for the simulation engine to start running immediately."""
        cast = await self._generate_cast(blueprint, count, proposed_change, segments, demographics)
        agents = await self._generate_personas(blueprint, cast, on_citizen)
        if proposed_change:
            self._assign_knowledge_levels(agents)
        return agents

    async def enrich_background(
        self,
        blueprint: WorldBlueprint,
        agents: list[AgentPersona],
    ) -> list[AgentPersona]:
        """Phase 2: add life histories + relationships. Can run concurrently
        while the simulation is already ticking. Agents are mutated in place."""
        await self._generate_life_histories(blueprint, agents)
        self._apply_all_trait_modifiers(agents)
        self._enforce_life_diversity(agents)
        agents = await self._generate_relationships(blueprint, agents)
        return agents

    @staticmethod
    def _assign_knowledge_levels(agents: list[AgentPersona]):
        """Not everyone knows about the change on day 1. Heavy users and
        price-sensitive consumers find out immediately; casual/low-engagement
        consumers may be unaware and must learn through gossip or research."""
        for agent in agents:
            p = agent.personality
            if p.price_sensitivity > 0.7 or p.brand_loyalty > 0.7 or p.ambition > 0.7:
                agent.knowledge_level = "full"
            elif p.novelty_seeking > 0.6 or p.social_proof > 0.6:
                agent.knowledge_level = "partial"
            else:
                agent.knowledge_level = random.choice(["partial", "unaware"])

    async def _generate_cast(
        self,
        blueprint: WorldBlueprint,
        count: int,
        proposed_change: str | None = None,
        segments: list[dict] | None = None,
        demographics: DemographicProfile | None = None,
    ) -> list[dict]:
        world_context = (
            f"World: {blueprint.name}\n"
            f"Description: {blueprint.description}\n"
            f"Rules: {'; '.join(blueprint.rules)}\n"
            f"Resources: {', '.join(blueprint.resources)}\n"
            f"Tensions: {'; '.join(blueprint.initial_tensions)}"
        )

        if demographics:
            age_dist = "\n".join(
                f"  - {a.bracket}: {a.percentage:.1f}%" for a in demographics.age
            ) or "  (not available)"
            occ_dist = "\n".join(
                f"  - {o.category}: {o.percentage:.1f}%" for o in demographics.occupations
            ) or "  (not available)"
            eth_dist = "\n".join(
                f"  - {e.group}: {e.percentage:.1f}%" for e in demographics.ethnicity
            ) or "  (not available)"
            char_line = f"CITY CHARACTER: {demographics.city_character}" if demographics.city_character else ""

            system_prompt = DEMOGRAPHIC_CAST_PROMPT.format(
                city_name=demographics.city_name,
                state=demographics.state,
                population=demographics.population,
                median_income=demographics.median_household_income,
                poverty_rate=demographics.poverty_rate,
                unemployment_rate=demographics.unemployment_rate,
                median_age=demographics.median_age,
                age_dist=age_dist,
                occ_dist=occ_dist,
                eth_dist=eth_dist,
                city_character=char_line,
            )
        else:
            system_prompt = CAST_SYSTEM_PROMPT

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
            system=system_prompt,
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

                raw_style = member.get("communication_style", "").lower().strip()
                comm_style = raw_style if raw_style in COMMUNICATION_STYLES else random.choice(list(COMMUNICATION_STYLES.keys()))

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
                    communication_style=comm_style,
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

        self._build_social_graph(agent_map)
        return list(agent_map.values())

    @staticmethod
    def _build_social_graph(agent_map: dict[int, AgentPersona]):
        POSITIVE_KEYWORDS = {"friend", "ally", "family", "mentor", "partner", "trust", "close", "love", "respect", "admire"}
        NEGATIVE_KEYWORDS = {"rival", "distrust", "resent", "enemy", "compete", "suspicious", "tension", "conflict", "dislikes"}

        for aid, agent in agent_map.items():
            edges: list[SocialEdge] = []
            for target_key, description in agent.relationships.items():
                try:
                    target_id = int(target_key)
                except (ValueError, TypeError):
                    continue
                if target_id not in agent_map:
                    continue

                desc_lower = description.lower()
                is_positive = any(kw in desc_lower for kw in POSITIVE_KEYWORDS)
                is_negative = any(kw in desc_lower for kw in NEGATIVE_KEYWORDS)

                if is_positive and not is_negative:
                    strength = round(0.6 + random.random() * 0.2, 2)
                    sentiment = round(0.3 + random.random() * 0.4, 2)
                elif is_negative and not is_positive:
                    strength = round(0.3 + random.random() * 0.2, 2)
                    sentiment = round(-0.3 - random.random() * 0.4, 2)
                else:
                    strength = round(0.4 + random.random() * 0.2, 2)
                    sentiment = round(-0.1 + random.random() * 0.2, 2)

                edges.append(SocialEdge(
                    target_id=target_id,
                    strength=strength,
                    sentiment=sentiment,
                ))
            agent.social_connections = edges

    async def _generate_life_histories(
        self, blueprint: WorldBlueprint, agents: list[AgentPersona]
    ) -> None:
        batch_size = 5
        for batch_start in range(0, len(agents), batch_size):
            batch = agents[batch_start:batch_start + batch_size]
            prompts = []
            for agent in batch:
                num_events = self._num_formative_events(agent.age)
                system = LIFE_HISTORY_PROMPT.format(num_events=num_events)
                world_ctx = (
                    f"World: {blueprint.name}\n"
                    f"Rules: {'; '.join(blueprint.rules)}\n"
                    f"Tensions: {'; '.join(blueprint.initial_tensions)}"
                )
                agent_ctx = (
                    f"Name: {agent.name}\n"
                    f"Role: {agent.role}\n"
                    f"Age: {agent.age}\n"
                    f"Background: {agent.background}\n"
                    f"Personality: honesty={agent.personality.honesty:.2f}, "
                    f"ambition={agent.personality.ambition:.2f}, "
                    f"empathy={agent.personality.empathy:.2f}, "
                    f"confrontational={agent.personality.confrontational:.2f}, "
                    f"conformity={agent.personality.conformity:.2f}\n"
                    f"Goals: {'; '.join(agent.goals)}\n"
                    f"Beliefs: {'; '.join(agent.beliefs)}"
                )
                prompts.append((system, f"{world_ctx}\n\n{agent_ctx}"))

            responses = await self.llm.generate_batch(prompts, json_mode=True, max_tokens=1200)

            for i, response in enumerate(responses):
                agent = batch[i]
                data = parse_json(response)
                agent.life_state = self._parse_life_history(data, agent)

    def _parse_life_history(self, data: dict, agent: AgentPersona) -> LifeState:
        formative_raw = data.get("formative_events", [])
        formative_events = []
        for ev in formative_raw:
            if not isinstance(ev, dict):
                continue
            modifier = ev.get("trait_modifier", {})
            if not isinstance(modifier, dict):
                modifier = {}
            formative_events.append(FormativeEvent(
                age_at_event=int(ev.get("age_at_event", 10)),
                description=str(ev.get("description", "A formative moment")),
                lasting_effect=str(ev.get("lasting_effect", "Shaped their worldview")),
                trait_modifier={str(k): float(v) for k, v in modifier.items()
                                if isinstance(v, (int, float))},
            ))

        family_raw = data.get("family", [])
        family = []
        for fm in family_raw:
            if not isinstance(fm, dict):
                continue
            family.append(FamilyMember(
                name=str(fm.get("name", "Unknown")),
                relation=str(fm.get("relation", "relative")),
                age=int(fm.get("age", 30)),
                status=str(fm.get("status", "healthy")),
                dependency=self._clamp(fm.get("dependency", 0.0)),
                bond_strength=self._clamp(fm.get("bond_strength", 0.7)),
            ))

        pressures_raw = data.get("initial_pressures", [])
        pressures = []
        for pr in pressures_raw:
            if not isinstance(pr, dict):
                continue
            pressures.append(LifePressure(
                domain=str(pr.get("domain", "finances")),
                description=str(pr.get("description", "An ongoing concern")),
                severity=self._clamp(pr.get("severity", 0.5)),
                created_day=0,
            ))

        return LifeState(
            childhood_summary=str(data.get("childhood_summary", f"{agent.name} had an unremarkable childhood.")),
            formative_events=formative_events,
            family=family,
            finances=self._clamp(data.get("finances", 0.5)),
            career=self._clamp(data.get("career", 0.5)),
            health=self._clamp(data.get("health", 0.5)),
            pressures=pressures,
        )

    def _apply_trait_modifiers(self, agent: AgentPersona) -> None:
        if not agent.life_state:
            return
        hit_counts: dict[str, int] = {}
        for event in agent.life_state.formative_events:
            for trait, delta in event.trait_modifier.items():
                hits = hit_counts.get(trait, 0)
                damping = 1.0 / (1 + hits * 0.5)
                current = getattr(agent.personality, trait, None)
                if current is None:
                    continue
                new_val = max(0.0, min(1.0, current + delta * damping))
                setattr(agent.personality, trait, round(new_val, 4))
                hit_counts[trait] = hits + 1

    def _apply_all_trait_modifiers(self, agents: list[AgentPersona]) -> None:
        for agent in agents:
            self._apply_trait_modifiers(agent)

    def _enforce_life_diversity(self, agents: list[AgentPersona]) -> None:
        life_agents = [a for a in agents if a.life_state]
        if not life_agents:
            return

        avg_finances = sum(a.life_state.finances for a in life_agents) / len(life_agents)
        if avg_finances < 0.35:
            sorted_by_fin = sorted(life_agents, key=lambda a: a.life_state.finances, reverse=True)
            top_quartile = sorted_by_fin[:max(1, len(sorted_by_fin) // 4)]
            for a in top_quartile:
                a.life_state.finances = round(random.uniform(0.6, 0.85), 2)

        avg_health = sum(a.life_state.health for a in life_agents) / len(life_agents)
        if avg_health < 0.4:
            sorted_by_health = sorted(life_agents, key=lambda a: a.life_state.health, reverse=True)
            top_third = sorted_by_health[:max(1, len(sorted_by_health) // 3)]
            for a in top_third:
                a.life_state.health = round(random.uniform(0.7, 0.95), 2)

        all_have_pressures = all(len(a.life_state.pressures) > 0 for a in life_agents)
        if all_have_pressures:
            num_to_clear = max(1, int(len(life_agents) * 0.2))
            to_clear = random.sample(life_agents, num_to_clear)
            for a in to_clear:
                a.life_state.pressures = []

        all_have_family = all(len(a.life_state.family) > 0 for a in life_agents)
        if all_have_family:
            young_agents = [a for a in life_agents if a.age < 30]
            num_to_reduce = max(1, int(len(young_agents) * 0.15)) if young_agents else 0
            if num_to_reduce and young_agents:
                to_reduce = random.sample(young_agents, min(num_to_reduce, len(young_agents)))
                for a in to_reduce:
                    a.life_state.family = [
                        f for f in a.life_state.family if f.relation in ("parent", "mother", "father")
                    ]

    def _num_formative_events(self, age: int) -> int:
        if age < 30:
            return 4
        if age < 50:
            return 5
        return 6

    @staticmethod
    def _clamp(v, lo=0.0, hi=1.0) -> float:
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return 0.5
