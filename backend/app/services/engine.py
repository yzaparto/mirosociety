from __future__ import annotations
import asyncio
import logging
import random
from typing import Callable, Awaitable, Any

from app.models.agent import AgentPersona, COMMUNICATION_STYLES
from app.models.action import ActionType, AgentDecision, ActionEntry, ReactiveResponse
from app.models.world import WorldState, WorldMetrics
from app.models.simulation import SimulationStatus, SpeedMode, SSEEvent
from app.db.store import SimulationStore
from app.services.llm import LLMClient, parse_json
from app.services.tension import TensionEngine
from app.services.resolver import ActionResolver
from app.services.narrator import Narrator
from app.services.research import ResearchService
from app.services.gossip import GossipEngine
from app.services.life_context import build_life_prompt_block, compute_action_bias
from app.services.life_engine import LifeEngine
from app.constants import TIMES_OF_DAY

logger = logging.getLogger(__name__)

AGENT_DECISION_SYSTEM = """You are {name}, a {age}-year-old {role} in {world_name}.

THE RULES OF THIS WORLD:
{rules}

WHO YOU ARE:
{background}
Personality: honesty={honesty:.1f}, ambition={ambition:.1f}, empathy={empathy:.1f}, confrontational={confrontational:.1f}, conformity={conformity:.1f}
{market_personality}

YOUR COMMUNICATION STYLE: {communication_style}

{life_context}
WHAT YOU KNOW TO BE TRUE (core memories):
{core_memory}

WHAT YOU BELIEVE RIGHT NOW:
{beliefs}

YOUR RELATIONSHIPS:
{relationships}

WHAT JUST HAPPENED (recent days):
{working_memory}
{market_context}

{recent_conversation}

THE SITUATION RIGHT NOW:
It is {time_of_day} on day {day}.
{context}

AVAILABLE ACTIONS (pick exactly one):
{actions}

{behavior_rules}

NOTE: Doing nothing is a perfectly valid choice. Not everyone acts every round. If nothing has changed since your last action and you have nothing new to say, choose OBSERVE or DO_NOTHING. The world doesn't need your opinion on everything. Silence and inaction are realistic.

FORBIDDEN: NEVER start speech with "I totally agree", "I completely agree", or similar empty validation. If you agree, add something NEW.

Think step by step:
1. FEEL: What is your emotional reaction to the current situation?
2. LIFE: How does your current life situation (family, money, health, pressures) affect how you see this?
3. PAST: Does anything in your history make you react differently than most people would?
4. WANT: Given your personality and goals, what do you want right now?
5. FEAR: What could go wrong? What worries you?
6. DECIDE: What action do you take? (Consider: have you already said this? Is DO_NOTHING or OBSERVE more appropriate?)

Respond as JSON:
{{
  "feel": "one sentence emotional reaction",
  "life_context": "how your life situation influences this moment, or null",
  "past_echo": "what past experience is triggered here, or null",
  "want": "one sentence desire",
  "fear": "one sentence concern",
  "action": "ACTION_TYPE",
  "args": {{ action-specific arguments }},
  "speech": "what you say out loud, or null if silent",
  "internal_thought": "what you think but don't say",
  "belief_updates": ["any changed beliefs"],
  "memory_promotion": "a core fact to remember long-term, or null"
}}

Action args by type:
- SPEAK_PUBLIC: {{}} (speech field is the content)
- SPEAK_PRIVATE: {{"target_id": agent_id}}
- TRADE: {{"target_id": agent_id, "give_resource": "name", "give_amount": N, "receive_resource": "name", "receive_amount": N}}
- FORM_GROUP: {{"name": "group name", "purpose": "why"}}
- PROPOSE_RULE: {{"content": "the rule"}}
- VOTE: {{"proposal_id": "id", "vote": "for" or "against"}}
- PROTEST: {{"target": "what you're protesting"}}
- COMPLY: {{}}
- DEFECT: {{"rule": "which rule you're breaking", "how": "what you do"}}
- BUILD: {{"what": "description", "resource": "name", "cost": N}}
- OBSERVE: {{}}
- RECOMMEND: {{"target_id": agent_id, "product": "what you recommend", "reason": "why"}}
- PURCHASE: {{"product": "what you buy", "amount": N}}
- ABANDON: {{"product": "what you stop using", "reason": "why you leave"}}
- COMPARE: {{"product_a": "first product", "product_b": "second product", "verdict": "your comparison"}}
- RESEARCH: {{"query": "what to search the internet for", "reason": "why you need this info"}}
  (Use when you need REAL facts — prices, reviews, competitor info, news — to make a better decision. You'll get actual search results next round.)
- INVESTIGATE: {{"target_id": agent_id, "question": "what you want to ask them"}}
  (Use when you want to deliberately seek out a specific person and ask them something directly. They will answer honestly or not, depending on who they are.)
- DO_NOTHING: {{}}

Return ONLY valid JSON."""

BEHAVIOR_RULES_SOCIAL = """IMPORTANT RULES FOR YOUR BEHAVIOR:
- Do NOT repeat things you've already said. Check your working memory.
- If you've already stated your position, either advance it with specifics, propose concrete action, respond to something new, or do something different.
- If everyone around you agrees, be suspicious — introduce nuance or a counterpoint.
- Conversation is how societies function. Debate, argue, persuade, gossip, confide. SPEAK_PUBLIC and SPEAK_PRIVATE are your primary tools — use them most of the time.
- Only escalate to FORM_GROUP, PROPOSE_RULE, or PROTEST when conversation has clearly failed or a specific situation demands organized action. Do NOT form a group unless you have a concrete, specific reason that existing groups don't cover.
- React to EVENTS when they happen — they change your situation.
- Before forming strong opinions, consider whether you actually KNOW the facts or are just assuming. If you're uncertain, RESEARCH to find real information or INVESTIGATE someone who might know.
- If someone makes a claim you doubt, you can INVESTIGATE them directly or RESEARCH the claim."""

BEHAVIOR_RULES_MARKET = """IMPORTANT RULES FOR YOUR BEHAVIOR:
- You are a CONSUMER with opinions. Talk to people, argue, convince, warn, commiserate — and also act.
- CRITICAL: CHECK YOUR WORKING MEMORY before choosing an action. If you already did something (compared, protested, researched), do NOT do it again. Move forward instead.
- Mix talking and action. A natural consumer both talks about their experience AND makes decisions.
- DECISION PROGRESSION — follow this natural path, don't get stuck:
  1. REACT (SPEAK_PUBLIC) — share your first feelings, respond to what others said
  2. GATHER INFO (COMPARE or RESEARCH) — do this ONCE, not repeatedly
  3. DECIDE (PURCHASE to stay, ABANDON to leave, DEFECT to switch, COMPLY to accept)
  4. INFLUENCE (RECOMMEND to a friend, SPEAK_PRIVATE to warn/gossip)
  If you've already done step 2, you MUST move to step 3 or 4. No more gathering info.
- Use SPEAK_PUBLIC to share opinions, react to others, argue, give reviews, or vent.
- Use SPEAK_PRIVATE to confide in someone, warn a friend, or gossip.
- Use COMPARE ONCE to evaluate alternatives. After comparing, DECIDE — don't compare again.
- Use PURCHASE when you commit to the product/brand.
- Use ABANDON when you leave or cancel. State your specific reason.
- Use DEFECT when you actively switch to a competitor. Say what you're switching to.
- Use RECOMMEND to personally influence someone. Be specific about who and why.
- Use PROTEST when genuinely unhappy — but don't protest the same thing twice. Escalate or move on.
- If an EVENT happens, react to it — talk about it AND let it change your behavior.
- FORBIDDEN PHRASES: NEVER start with "I totally agree", "I completely agree", "I couldn't agree more", "I feel the same way", or any variant. If you agree, show it through ACTION or by adding something genuinely NEW.
- If everyone around you agrees, be suspicious. Introduce nuance, ask a hard question, or play devil's advocate.

ANTI-CASCADE RULE — READ CAREFULLY:
- NOT everyone leaves. In real life, most consumers STAY even when upset. Complaining is NOT the same as leaving.
- COMPLY is a valid and COMMON decision. Most real people grumble, adapt, and keep their subscription.
- Only ABANDON or DEFECT if YOUR specific personality traits (price_sensitivity, brand_loyalty) strongly push you there.
- If other people are leaving, that does NOT mean you should. Think for YOURSELF based on YOUR traits.
- PURCHASE/COMPLY/OBSERVE are realistic outcomes for loyal or moderate consumers.

YOUR TRAITS DETERMINE YOUR OUTCOME (this is binding, not a suggestion):
  * brand_loyalty >= 0.7 → you MUST end at COMPLY or PURCHASE. Defend the brand. Find reasons to stay. Others leaving makes you SAD, not motivated to follow them.
  * brand_loyalty 0.4-0.7 → you complain but likely stay. COMPLY is your most probable outcome unless the change personally affects your budget.
  * price_sensitivity >= 0.7 → you progress fast, end at ABANDON or DEFECT quickly.
  * price_sensitivity < 0.4 → price changes barely register for you. You stay.
  * social_proof >= 0.7 → you follow the MAJORITY, not the loudest voices. If most people are still subscribed, you stay. Only follow exits after a clear tipping point (3+ people you know personally).
  * novelty_seeking >= 0.7 → you're excited by alternatives, but consider DIFFERENT competitors — not just whatever everyone else picks.
- Before forming strong opinions, RESEARCH to find real information or INVESTIGATE someone who might know.
- If someone makes a claim you doubt, INVESTIGATE them or RESEARCH the claim.
- CONTENT LOOP: Do NOT repeat the same talking point (e.g. same analogy, same complaint) across rounds. Say something new or stay silent.
{repetition_warning}"""

REACTIVE_PROMPT_SOCIAL = """You are {name}, a {role} in {world_name}.
Your mood: {mood}.
Personality: conformity={conformity:.1f}, confrontational={confrontational:.1f}, empathy={empathy:.1f}
{market_traits}
{faction_info}
{conformity_nudge}

YOUR COMMUNICATION STYLE: {communication_style}

YOUR BELIEFS:
{beliefs}

YOUR RECENT EXPERIENCE:
{recent_memory}

You just heard {speaker} say: "{content}"

Most people stay silent — only speak if you have something genuinely different to add.

How do you react? React based on YOUR beliefs, personality, and communication style — not to be polite.
Disagreement, skepticism, sarcasm, deflection, and changing the subject are all valid.
NEVER start with "I totally agree" or similar. If you agree, add something new — a personal story, a hard question, a specific detail.
Only agree if you genuinely would based on your beliefs.

(a) Respond publicly — say something everyone can hear
(b) Whisper privately — say something only to someone near you
(c) Stay silent — keep your thoughts to yourself

Reply with ONLY the letter and your response (1-2 sentences max).
Examples: "a That's easy to say when you're not the one paying for it." or "b I don't buy what they're selling — do you?" or "c" """

REACTIVE_PROMPT_MARKET = """You are {name}, a {role} in {world_name}.
Your mood: {mood}.
Personality: conformity={conformity:.1f}, confrontational={confrontational:.1f}, empathy={empathy:.1f}
Consumer traits: brand_loyalty={brand_loyalty:.1f}, price_sensitivity={price_sensitivity:.1f}, social_proof={social_proof:.1f}, novelty_seeking={novelty_seeking:.1f}
{faction_info}
{conformity_nudge}

YOUR COMMUNICATION STYLE: {communication_style}

YOUR BELIEFS:
{beliefs}

YOUR RECENT EXPERIENCE:
{recent_memory}

You just heard {speaker} say: "{content}"

Most people stay silent when they hear something — silence is the most common human reaction. Only speak if you have something genuinely different to add.

React as a REAL CONSUMER with your specific communication style, not a debate partner. Consider:
- Does this make you more or less likely to buy/stay/leave?
- Would you tell a friend about this? Would you warn them?
- Are you annoyed, excited, indifferent, or worried?

Be specific and personal. Reference your own experience with the product/brand.
NEVER start with "I totally agree", "I completely agree", or similar. If you agree, show it by adding a personal story, specific detail, or new angle — not by restating what was said.
Don't give generic "balance" takes — say what you'd actually say as a customer.

(a) Respond publicly — say something everyone can hear
(b) Whisper privately — say something only to someone near you
(c) Stay silent — keep your thoughts to yourself

Reply with ONLY the letter and your response (1-2 sentences max).
Examples: "a I already cancelled my order — this new logo looks like a toy brand." or "b Honestly? I'm looking at Rivian now." or "c" """


REACTIVE_ACTION_PROMPT = """You are {name}, a {role} in {world_name}.
Your mood: {mood}.
Personality: conformity={conformity:.1f}, confrontational={confrontational:.1f}, empathy={empathy:.1f}
{market_traits}
{faction_info}
{conformity_nudge}

YOUR COMMUNICATION STYLE: {communication_style}

YOUR BELIEFS:
{beliefs}

YOUR RECENT EXPERIENCE:
{recent_memory}

You just witnessed {actor} {action_description}

Most people say nothing when they see someone act. Only react if this genuinely affects you.

React naturally as yourself using your communication style. You might:
- Challenge or support their decision
- Share your own experience or plans
- Try to persuade them to stay/go/reconsider
- Express surprise, sympathy, or frustration
- Ask them why

Be specific and personal. Don't be generic. NEVER start with "I totally agree" or similar.

(a) Respond publicly — say something everyone can hear
(b) Whisper privately — say something only to someone near you
(c) Stay silent — keep your thoughts to yourself

Reply with ONLY the letter and your response (1-2 sentences max).
Examples: "a Wait, you're actually leaving? I was thinking about it too but I'm not sure yet." or "b Honestly, I think they're right to go." or "c" """

INVESTIGATE_PROMPT = """You are {target_name}, a {target_age}-year-old {target_role} in {world_name}.
Your mood: {mood}.
Personality: honesty={honesty:.1f}, confrontational={confrontational:.1f}, empathy={empathy:.1f}, conformity={conformity:.1f}
{market_traits}

Your current beliefs:
{beliefs}

Your recent experience:
{recent_memory}

{agent_name} approaches you and asks: "{question}"

Your relationship with {agent_name}: {relationship}

Answer IN CHARACTER. Based on your personality:
- If honesty is high, answer truthfully even if it's uncomfortable
- If honesty is low, you may deflect, lie, or give a partial answer
- If confrontational is high, you may push back on the question itself
- If empathy is high, consider how your answer affects {agent_name}

Reply with 1-2 sentences. Just your spoken answer, nothing else."""


class SimulationEngine:
    def __init__(
        self,
        llm: LLMClient,
        store: SimulationStore,
        tension: TensionEngine,
        resolver: ActionResolver,
        narrator: Narrator,
        research: ResearchService | None = None,
        gossip: GossipEngine | None = None,
        life_engine: LifeEngine | None = None,
    ):
        self.llm = llm
        self.store = store
        self.tension = tension
        self.resolver = resolver
        self.narrator = narrator
        self.research = research
        self.gossip = gossip or GossipEngine()
        self.life_engine = life_engine
        self._running: dict[str, bool] = {}
        self._paused: dict[str, asyncio.Event] = {}
        self._speed: dict[str, SpeedMode] = {}
        self._total_actions: dict[str, int] = {}
        self._last_narrative: dict[str, str] = {}
        self._enriched_agents: dict[str, list[AgentPersona]] = {}
        self._enrichment_ready: dict[str, asyncio.Event] = {}

    async def _wait_if_paused(self, simulation_id: str) -> bool:
        """Block while paused. Returns False if the simulation was stopped."""
        if simulation_id not in self._paused:
            return False
        await self._paused[simulation_id].wait()
        return self._running.get(simulation_id, False)

    def deliver_enriched_agents(self, simulation_id: str, agents: list[AgentPersona]):
        """Called from outside when background enrichment finishes. The engine
        will hot-swap the agent list at the start of the next round."""
        self._enriched_agents[simulation_id] = agents
        ev = self._enrichment_ready.get(simulation_id)
        if ev:
            ev.set()

    def _check_enrichment(self, simulation_id: str, agents: list[AgentPersona]) -> list[AgentPersona]:
        """If enriched agents have arrived, merge life_state, social_connections,
        and relationships into the live agent list (preserving working_memory,
        core_memory, beliefs, resources, and other mutable state accumulated
        during the first rounds)."""
        enriched = self._enriched_agents.pop(simulation_id, None)
        if enriched is None:
            return agents
        enriched_map = {a.id: a for a in enriched}
        for agent in agents:
            src = enriched_map.get(agent.id)
            if src is None:
                continue
            agent.life_state = src.life_state
            agent.social_connections = src.social_connections
            if src.relationships:
                agent.relationships = src.relationships
        logger.info("Enriched %d agents for sim %s", len(enriched_map), simulation_id)
        return agents

    async def run(
        self,
        simulation_id: str,
        world_state: WorldState,
        agents: list[AgentPersona],
        emit: Callable[[SSEEvent], Awaitable[None]],
        start_round: int = 0,
    ):
        self._running[simulation_id] = True
        self._paused[simulation_id] = asyncio.Event()
        self._paused[simulation_id].set()
        self._speed[simulation_id] = SpeedMode.LIVE
        self._total_actions[simulation_id] = 0
        self._last_narrative[simulation_id] = ""
        self._enrichment_ready[simulation_id] = asyncio.Event()
        self.gossip.init_simulation(simulation_id)

        total_rounds = world_state.blueprint.time_config.total_days * world_state.blueprint.time_config.rounds_per_day
        round_num = start_round

        await self.store.save_world_state(simulation_id, round_num, world_state)
        await self.store.save_agents_batch(simulation_id, agents)

        try:
            while round_num < total_rounds and self._running.get(simulation_id, False):
                if not await self._wait_if_paused(simulation_id):
                    break

                agents = self._check_enrichment(simulation_id, agents)

                round_num += 1
                world_state.round_in_day = (round_num - 1) % world_state.blueprint.time_config.rounds_per_day
                world_state.day = (round_num - 1) // world_state.blueprint.time_config.rounds_per_day + 1

                tension_event = None
                sig_count = self._count_significant(await self.store.get_actions(
                    simulation_id, max(0, round_num - 6), round_num - 1
                )) if round_num > 1 else 0

                world_state, agents, tension_event = await self.tension.check_and_apply(
                    world_state, agents, sig_count, sim_id=simulation_id
                )

                if not await self._wait_if_paused(simulation_id):
                    break

                active = self._select_active_agents(world_state, agents, round_num, tension_event is not None)

                life_events_this_round = []
                if self.life_engine:
                    try:
                        life_events_this_round = await self.life_engine.evaluate(agents, world_state, round_num)
                        for agent, event_desc in life_events_this_round:
                            agent.working_memory.append(f"Day {world_state.day}: {event_desc}")
                            if len(agent.working_memory) > 9:
                                agent.working_memory = agent.working_memory[-9:]
                    except Exception as life_err:
                        logger.warning("LifeEngine failed for round %d: %s", round_num, life_err)

                decisions = await self._batch_decisions(active, world_state, agents)

                if not await self._wait_if_paused(simulation_id):
                    break

                resolved_entries, world_state, agents = self.resolver.resolve(
                    decisions, world_state, agents, round_num
                )

                if self.research:
                    resolved_entries = await self._fulfill_research(
                        resolved_entries, agents, world_state
                    )

                speech_actions = [
                    e for e in resolved_entries
                    if e.action_type in (ActionType.SPEAK_PUBLIC, ActionType.SPEAK_PRIVATE) and e.speech
                ]

                conversational_actions = [
                    e for e in resolved_entries
                    if e.action_type in (
                        ActionType.PROTEST, ActionType.ABANDON, ActionType.DEFECT,
                        ActionType.RECOMMEND, ActionType.COMPARE, ActionType.PURCHASE,
                    ) and e not in speech_actions
                ]

                reactions: list[ReactiveResponse] = []
                if speech_actions:
                    reactions = await self._reactive_micro_round(speech_actions, agents, world_state)
                if conversational_actions:
                    action_reactions = await self._reactive_micro_round_actions(
                        conversational_actions, agents, world_state
                    )
                    reactions.extend(action_reactions)

                if not await self._wait_if_paused(simulation_id):
                    break

                self._total_actions[simulation_id] += len(resolved_entries)

                narrative = ""
                try:
                    narrative = await self.narrator.narrate_round(
                        world_state,
                        resolved_entries,
                        reactions=reactions or None,
                        previous_narrative=self._last_narrative.get(simulation_id) or None,
                        tension_event=tension_event,
                    )
                    if narrative:
                        self._last_narrative[simulation_id] = narrative
                        tod = TIMES_OF_DAY[world_state.round_in_day % 3]
                        await self.store.save_narrative(simulation_id, round_num, world_state.day, tod, narrative)
                except Exception as narr_err:
                    logger.warning("Narrator failed for round %d: %s", round_num, narr_err)

                for agent, event_desc in life_events_this_round:
                    await emit(SSEEvent(type="life_event", data={
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "event_description": event_desc,
                        "day": world_state.day,
                        "time_of_day": TIMES_OF_DAY[world_state.round_in_day % 3],
                    }))

                is_market_sim = self._is_market_simulation(world_state)
                tod = TIMES_OF_DAY[world_state.round_in_day % 3]

                self.gossip.propagate(
                    sim_id=simulation_id,
                    resolved_entries=resolved_entries,
                    reactions=reactions,
                    agents=agents,
                    round_num=round_num,
                    day=world_state.day,
                    time_of_day=tod,
                    is_market=is_market_sim,
                )

                if tension_event:
                    event_recipients = self.tension.get_event_recipients()
                    self.gossip.inject_event_via_gossip(
                        sim_id=simulation_id,
                        event_desc=tension_event,
                        agents=agents,
                        round_num=round_num,
                        day=world_state.day,
                        initial_recipients=event_recipients,
                    )

                gossip_metrics = self.gossip.compute_gossip_metrics(simulation_id, agents, round_num)
                world_state.metrics.information_spread = gossip_metrics["information_spread"]
                world_state.metrics.echo_chamber_index = gossip_metrics["echo_chamber_index"]
                world_state.metrics.rumor_distortion = gossip_metrics["rumor_distortion"]

                if world_state.day % 30 == 0 and world_state.round_in_day == 0:
                    await self._reflective_memory_pass(simulation_id, agents, world_state)

                await self.store.save_world_state(simulation_id, round_num, world_state)
                await self.store.save_agents_batch(simulation_id, agents)
                await self.store.save_actions_batch(simulation_id, resolved_entries)
                await self.store.save_metrics(simulation_id, round_num, world_state.metrics)

                significance = self._count_significant(resolved_entries)

                await emit(SSEEvent(
                    type="round_complete",
                    data={
                        "round": round_num,
                        "day": world_state.day,
                        "time_of_day": TIMES_OF_DAY[world_state.round_in_day % 3],
                        "actions": [e.model_dump() for e in resolved_entries],
                        "reactions": [r.model_dump() for r in reactions],
                        "metrics": world_state.metrics.model_dump(),
                        "tension_event": tension_event,
                        "narrative": narrative,
                        "significance": significance,
                        "agents_active": len(active),
                        "agents": [
                            {"id": a.id, "name": a.name, "location": a.location,
                             "emotional_state": a.emotional_state, "faction": a.faction,
                             "role": a.role,
                             "core_memory": a.core_memory,
                             "beliefs": a.beliefs,
                             "working_memory": a.working_memory,
                             "goals": a.goals,
                             "communication_style": getattr(a, "communication_style", "emotional"),
                             "knowledge_level": getattr(a, "knowledge_level", "full"),
                             "social_connections": [
                                 {"target_id": e.target_id, "strength": round(e.strength, 2), "sentiment": round(e.sentiment, 2)}
                                 for e in a.social_connections
                             ]}
                            for a in agents
                        ],
                        "institutions": [i.model_dump() for i in world_state.institutions],
                        "proposals": [p.model_dump() for p in world_state.proposals if p.status == "open"],
                    },
                ))

                await self.store.update_status(
                    simulation_id, SimulationStatus.RUNNING.value,
                    world_name=world_state.blueprint.name,
                    agent_count=len(agents),
                )

                speed = self._speed.get(simulation_id, SpeedMode.LIVE)
                if speed == SpeedMode.LIVE:
                    await asyncio.sleep(2.5)
                elif speed == SpeedMode.FAST_FORWARD:
                    await asyncio.sleep(0.5)
                elif speed == SpeedMode.JUMP:
                    await asyncio.sleep(0.1)

            await emit(SSEEvent(
                type="simulation_complete",
                data={
                    "total_rounds": round_num,
                    "total_days": world_state.day,
                    "total_actions": self._total_actions.get(simulation_id, 0),
                },
            ))
            await self.store.update_status(simulation_id, SimulationStatus.COMPLETED.value)
            asyncio.create_task(self._generate_report_background(simulation_id))

        except Exception as e:
            logger.error("Simulation %s failed: %s", simulation_id, e, exc_info=True)
            await emit(SSEEvent(type="error", data={"message": str(e)}))
            await self.store.update_status(simulation_id, SimulationStatus.ERROR.value)
            if self._total_actions.get(simulation_id, 0) > 0:
                asyncio.create_task(self._generate_report_background(simulation_id))
        finally:
            self._running.pop(simulation_id, None)
            self._paused.pop(simulation_id, None)
            self._speed.pop(simulation_id, None)
            self._total_actions.pop(simulation_id, None)
            self._last_narrative.pop(simulation_id, None)
            self._enriched_agents.pop(simulation_id, None)
            self._enrichment_ready.pop(simulation_id, None)
            self.tension.cleanup(simulation_id)
            self.gossip.cleanup(simulation_id)

    def _select_active_agents(
        self,
        world_state: WorldState,
        agents: list[AgentPersona],
        round_num: int,
        event_occurred: bool,
    ) -> list[AgentPersona]:
        tc = world_state.blueprint.time_config
        base_min = tc.active_agents_per_round_min
        base_max = tc.active_agents_per_round_max
        base_count = random.randint(base_min, base_max)

        bridge_node_ids = set(TensionEngine.find_bridge_nodes(agents))

        weights: dict[int, float] = {}
        has_open_proposals = any(p.status == "open" for p in world_state.proposals)

        is_market = self._is_market_simulation(world_state)

        for a in agents:
            w = 0.3 + a.personality.ambition * 0.2

            if a.emotional_state in ("restless", "dissatisfied", "frustrated", "angry", "fearful"):
                w += 0.3
            if has_open_proposals and a.faction:
                w += 0.2
            if event_occurred:
                w += 0.4

            if a.id in bridge_node_ids:
                w += 0.15

            if is_market:
                if a.personality.brand_loyalty > 0.7:
                    w += 0.15
                if a.personality.novelty_seeking > 0.7:
                    w += 0.1
                if a.personality.social_proof > 0.7 and world_state.metrics.word_of_mouth > 0.3:
                    w += 0.15

            weights[a.id] = min(1.0, w)

        selected: list[AgentPersona] = []
        pool = list(agents)
        max_active = max(base_count, int(len(agents) * 0.6))
        target = min(base_count + (3 if event_occurred else 0), max_active)

        for _ in range(target):
            if not pool:
                break
            ws = [weights.get(a.id, 0.3) for a in pool]
            total = sum(ws)
            if total == 0:
                break
            pick = random.choices(pool, weights=ws, k=1)[0]
            selected.append(pick)
            pool.remove(pick)

        return selected

    async def _batch_decisions(
        self,
        active_agents: list[AgentPersona],
        world_state: WorldState,
        all_agents: list[AgentPersona],
    ) -> list[tuple[AgentPersona, AgentDecision]]:
        prompts = []
        for agent in active_agents:
            prompt = self._build_decision_prompt(agent, world_state, all_agents)
            prompts.append(prompt)

        responses = await self.llm.generate_batch(prompts, json_mode=True, max_tokens=500)

        results: list[tuple[AgentPersona, AgentDecision]] = []
        for agent, response in zip(active_agents, responses):
            data = parse_json(response)
            if not data:
                results.append((agent, AgentDecision()))
                continue

            action_str = data.get("action", "DO_NOTHING")
            try:
                action = ActionType(action_str)
            except ValueError:
                action = ActionType.DO_NOTHING

            decision = AgentDecision(
                feel=data.get("feel", ""),
                want=data.get("want", ""),
                fear=data.get("fear", ""),
                life_context=data.get("life_context") or "",
                past_echo=data.get("past_echo") or "",
                action=action,
                args=data.get("args", {}),
                speech=data.get("speech"),
                internal_thought=data.get("internal_thought", ""),
                belief_updates=data.get("belief_updates", []),
                memory_promotion=data.get("memory_promotion"),
            )
            results.append((agent, decision))

        return results

    @staticmethod
    def _is_market_simulation(world_state: WorldState) -> bool:
        m = world_state.metrics
        has_market_resources = any(
            r in world_state.blueprint.resources
            for r in ("money", "satisfaction", "loyalty_points")
        )
        has_market_metrics = (
            m.adoption_rate > 0.0
            or m.churn_risk != 0.2
            or m.brand_sentiment != 0.5
        )
        return has_market_resources or has_market_metrics

    @staticmethod
    def _detect_repetition(agent: AgentPersona) -> str:
        warnings = []
        mem_lower = [m.lower() for m in agent.working_memory]

        compare_count = sum(1 for m in mem_lower if "compared" in m or "compare" in m)
        if compare_count >= 3:
            warnings.append(
                "\n🛑 You have compared options {n} times already. STOP COMPARING. "
                "You have enough information to DECIDE. You MUST now pick one: "
                "PURCHASE (commit to the product), ABANDON (leave it), DEFECT (switch to competitor), "
                "or SPEAK_PUBLIC (tell people your decision). No more comparing."
                .format(n=compare_count)
            )
        elif compare_count >= 2:
            warnings.append(
                "\n⚠️ You've already compared these options. Time to make a decision. "
                "Will you stay (PURCHASE/COMPLY), leave (ABANDON), switch (DEFECT), "
                "or tell someone what you decided (SPEAK_PUBLIC/RECOMMEND)?"
            )

        research_count = sum(1 for m in mem_lower if "research" in m)
        if research_count >= 2:
            warnings.append(
                "\n⚠️ You've done enough research. Use what you've learned to ACT — "
                "decide, switch, stay, or share your findings with someone."
            )

        protest_count = sum(1 for m in mem_lower if "protest" in m)
        if protest_count >= 2:
            warnings.append(
                "\n⚠️ You've already protested. Protesting again won't change things. "
                "Either escalate (DEFECT/ABANDON) or try something different (RECOMMEND an alternative, SPEAK_PRIVATE to organize)."
            )

        speech_count = sum(1 for m in mem_lower if "said" in m or "speak_public" in m)
        decisive_count = sum(1 for m in mem_lower if any(
            act in m for act in ("purchase", "abandon", "defect")
        ))

        if speech_count >= 4 and decisive_count == 0 and compare_count < 2:
            warnings.append(
                "\n💡 You've been talking a lot. Consider taking a concrete action — "
                "buy, leave, recommend, or protest. Actions speak louder than words."
            )

        content_warning = SimulationEngine._detect_content_repetition(mem_lower)
        if content_warning:
            warnings.append(content_warning)

        return warnings[0] if warnings else ""

    @staticmethod
    def _detect_content_repetition(mem_lower: list[str]) -> str:
        """Detect semantic content loops — agents repeating the same talking point
        across multiple rounds (e.g. Blockbuster analogy, family movie night, etc.)."""
        speech_memories = [m for m in mem_lower if "said" in m]
        if len(speech_memories) < 3:
            return ""

        phrase_counts: dict[str, int] = {}
        key_phrases = [
            "blockbuster", "family movie night", "loyal customer", "jumping ship",
            "squeeze every penny", "corporate greed", "password sharing",
            "price hike", "price increase", "ridiculous rules", "silly rules",
            "flexible sharing", "quality content", "premium content",
        ]
        for mem in speech_memories:
            for phrase in key_phrases:
                if phrase in mem:
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        repeated = [(p, c) for p, c in phrase_counts.items() if c >= 3]
        if repeated:
            top_phrase, count = max(repeated, key=lambda x: x[1])
            return (
                f"\n🔁 CONTENT LOOP DETECTED: You've mentioned '{top_phrase}' {count} times. "
                "STOP repeating yourself. Say something genuinely NEW, take a concrete action, "
                "or stay silent. Repeating the same point makes you boring and unrealistic."
            )

        word_bags: list[set[str]] = []
        for mem in speech_memories[-4:]:
            words = set(w for w in mem.split() if len(w) > 4)
            word_bags.append(words)

        if len(word_bags) >= 3:
            overlaps = []
            for i in range(len(word_bags)):
                for j in range(i + 1, len(word_bags)):
                    if word_bags[i] and word_bags[j]:
                        overlap = len(word_bags[i] & word_bags[j]) / min(len(word_bags[i]), len(word_bags[j]))
                        overlaps.append(overlap)
            if overlaps and sum(overlaps) / len(overlaps) > 0.5:
                return (
                    "\n🔁 You keep saying very similar things. Change the topic, take an action, "
                    "or choose DO_NOTHING. Real people don't repeat themselves this much."
                )

        return ""

    @staticmethod
    def _build_position_tracker(agent: AgentPersona, all_agents: list[AgentPersona]) -> str:
        """Show a BALANCED view of what others are doing — include stayers, not just leavers.
        Without balance, the tracker becomes a cascade amplifier that makes every remaining
        agent think "everyone is leaving" and follow suit."""
        left_names: list[str] = []
        stayed_names: list[str] = []
        talking_names: list[str] = []

        exit_keywords = ("abandon", "defect", "switched", "left", "jumping ship", "cancelled")
        stay_keywords = ("purchase", "comply", "recommend", "still worth", "staying")

        for other in all_agents:
            if other.id == agent.id:
                continue
            mem_lower = [m.lower() for m in other.working_memory]
            has_left = any(kw in m for m in mem_lower for kw in exit_keywords)
            has_stayed = any(kw in m for m in mem_lower for kw in stay_keywords)
            has_spoken = any("said" in m for m in mem_lower)

            if has_left:
                left_names.append(other.name)
            elif has_stayed:
                stayed_names.append(other.name)
            elif has_spoken:
                talking_names.append(other.name)

        total_others = len(all_agents) - 1
        if total_others <= 0:
            return ""

        parts = ["\nWHAT OTHERS ARE ACTUALLY DOING:"]
        if left_names:
            parts.append(f"- LEFT ({len(left_names)}/{total_others}): {', '.join(left_names[:4])}")
        if stayed_names:
            parts.append(f"- STAYED ({len(stayed_names)}/{total_others}): {', '.join(stayed_names[:4])}")

        undecided = total_others - len(left_names) - len(stayed_names)
        if undecided > 0:
            parts.append(f"- UNDECIDED ({undecided}/{total_others}): still talking or watching")

        if len(parts) <= 1:
            return ""
        return "\n".join(parts)

    @staticmethod
    def _loyalty_anchor(agent: AgentPersona) -> str:
        """Generate a personality-anchored constraint that resists uniform cascade behavior.
        High brand_loyalty agents get strong stay-pressure; high price_sensitivity agents
        get permission to leave quickly. Without this, the LLM treats all agents the same."""
        p = agent.personality
        parts = []

        if p.brand_loyalty >= 0.7:
            parts.append(
                "⚓ LOYALTY ANCHOR: You are deeply loyal to this brand. Switching feels like "
                "betraying something you believe in. You need OVERWHELMING, PERSONAL evidence "
                "to leave — other people complaining is NOT enough. You defend the brand, find "
                "silver linings, and end at COMPLY or PURCHASE. You do NOT follow the crowd."
            )
        elif p.brand_loyalty >= 0.5:
            parts.append(
                "⚓ LOYALTY: You have moderate brand attachment. You'll grumble but stay unless "
                "the change directly harms YOUR situation. Don't leave just because others are leaving."
            )

        if p.price_sensitivity >= 0.7:
            parts.append(
                "💰 PRICE PRESSURE: Price increases hit you hard. You move quickly to COMPARE "
                "and then ABANDON or DEFECT. You don't need to wait for others."
            )

        if p.social_proof >= 0.7:
            defect_count = sum(
                1 for m in agent.working_memory
                if any(w in m.lower() for w in ("abandon", "defect", "switched", "left", "jumping ship"))
            )
            if defect_count >= 3:
                parts.append(
                    "👥 SOCIAL TIPPING POINT: Multiple people you know have already left. "
                    "As someone who follows the crowd, this is now YOUR moment to decide."
                )
            elif defect_count >= 1:
                parts.append(
                    "👥 SOCIAL SIGNAL: A few people have left, but most haven't. "
                    "You follow the majority — and the majority is still here. Wait and see."
                )
            else:
                parts.append(
                    "👥 SOCIAL PROOF: Nobody around you has actually left yet. "
                    "People complain, but complaining isn't leaving. You wait for real action."
                )

        if p.novelty_seeking >= 0.7:
            parts.append(
                "🔍 NOVELTY: You're excited by alternatives. You want to try the new thing, "
                "but consider DIFFERENT competitors — not just whatever everyone else picks."
            )

        return "\n".join(parts)

    @staticmethod
    def _decision_stage_nudge(agent: AgentPersona) -> str:
        mem_lower = [m.lower() for m in agent.working_memory]
        has_compared = any("compared" in m or "compare" in m for m in mem_lower)
        has_researched = any("research" in m for m in mem_lower)
        has_protested = any("protest" in m for m in mem_lower)
        has_decided = any(
            act in m for m in mem_lower
            for act in ("purchase", "abandon", "defect", "switched", "cancelled", "left")
        )
        has_spoken = any("said" in m for m in mem_lower)

        p = agent.personality
        is_loyal = p.brand_loyalty >= 0.6

        if has_decided:
            return (
                "\nYOUR DECISION STAGE: You've already made a decision. "
                "Now influence others — RECOMMEND to a friend, share your experience (SPEAK_PUBLIC), "
                "or observe how others react."
            )
        if has_compared or has_researched:
            if is_loyal:
                return (
                    "\nYOUR DECISION STAGE: You've gathered info. Given your brand loyalty, "
                    "consider whether the brand still delivers value for YOU specifically. "
                    "Decide: PURCHASE (recommit), COMPLY (accept changes), or if truly untenable, ABANDON."
                )
            return (
                "\nYOUR DECISION STAGE: You've gathered enough information. "
                "It's time to DECIDE: PURCHASE (stay), ABANDON (leave), DEFECT (switch to competitor), "
                "or COMPLY (accept the changes). Stop researching and comparing — commit to a choice."
            )
        if has_protested:
            if is_loyal:
                return (
                    "\nYOUR DECISION STAGE: You've voiced your displeasure. "
                    "But you're loyal — consider whether this is truly a dealbreaker or just frustration. "
                    "You could COMPLY (grudgingly accept) or RESEARCH to see if the value is still there."
                )
            return (
                "\nYOUR DECISION STAGE: You've voiced your displeasure. "
                "Now either escalate (ABANDON/DEFECT) or reconsider (COMPARE alternatives, RESEARCH facts)."
            )
        if has_spoken:
            return (
                "\nYOUR DECISION STAGE: You've shared your initial reaction. "
                "Now gather info (COMPARE or RESEARCH once) or go straight to a decision if you've heard enough."
            )
        return ""

    def _build_decision_prompt(
        self,
        agent: AgentPersona,
        world_state: WorldState,
        all_agents: list[AgentPersona],
    ) -> tuple[str, str]:
        others = [a for a in all_agents if a.id != agent.id]
        nearby = self.gossip.social_neighbors(agent, all_agents, count=5)
        if not nearby:
            nearby = random.sample(others, min(5, len(others)))
        nearby_text = ", ".join(
            f"{a.name} ({a.role}, {a.emotional_state}" + (f", {a.faction}" if a.faction else "") + ")"
            for a in nearby[:5]
        ) or "no one"

        context_parts = [f"Nearby: {nearby_text}"]
        if world_state.active_disputes:
            context_parts.append(f"Active disputes: {'; '.join(world_state.active_disputes[:3])}")
        open_proposals = [p for p in world_state.proposals if p.status == "open"]
        if open_proposals:
            for p in open_proposals[:2]:
                context_parts.append(
                    f"Open proposal by agent {p.proposer_id}: \"{p.content}\" (for: {len(p.votes_for)}, against: {len(p.votes_against)})"
                )
        if world_state.institutions:
            inst_details = []
            for i in world_state.institutions:
                inst_details.append(f"{i.name} ({len(i.member_ids)} members, purpose: {i.purpose[:60]})")
            context_parts.append(f"Existing groups/institutions ({len(world_state.institutions)} total): {'; '.join(inst_details[:6])}")
            if len(world_state.institutions) >= 5:
                context_parts.append("NOTE: Many groups already exist. Consider joining one instead of founding another.")
        if world_state.community_rules:
            context_parts.append(f"Community rules in effect: {'; '.join(world_state.community_rules[-5:])}")

        event_disputes = [d for d in world_state.active_disputes if "EVENT" in d or "Disruption" in d]
        if event_disputes:
            context_parts.append(f"RECENT EVENT that just happened: {event_disputes[-1]}")

        is_market = self._is_market_simulation(world_state)
        market_actions = {
            ActionType.RECOMMEND, ActionType.PURCHASE,
            ActionType.ABANDON, ActionType.COMPARE,
        }

        available = list(ActionType)
        if not is_market:
            available = [a for a in available if a not in market_actions]
        if not open_proposals:
            available = [a for a in available if a != ActionType.VOTE]
        if not others:
            social_actions = {
                ActionType.SPEAK_PUBLIC, ActionType.SPEAK_PRIVATE,
                ActionType.TRADE, ActionType.FORM_GROUP, ActionType.PROTEST,
                ActionType.RECOMMEND, ActionType.INVESTIGATE,
            }
            available = [a for a in available if a not in social_actions]
        if not self.research or not self.research.enabled:
            available = [a for a in available if a != ActionType.RESEARCH]

        if is_market:
            mem_lower = [m.lower() for m in agent.working_memory]
            already_compared = sum(1 for m in mem_lower if "compared" in m or "compare" in m) >= 2
            already_researched = sum(1 for m in mem_lower if "research" in m) >= 2
            already_protested = sum(1 for m in mem_lower if "protest" in m) >= 2
            if already_compared:
                available = [a for a in available if a != ActionType.COMPARE]
            if already_researched:
                available = [a for a in available if a != ActionType.RESEARCH]
            if already_protested:
                available = [a for a in available if a != ActionType.PROTEST]

        action_bias: dict[str, str] = {}
        if agent.life_state is not None:
            action_bias = compute_action_bias(agent, world_state.day)

        if action_bias:
            actions_text = "\n".join(
                f"- {a.value} {action_bias.get(a.value, '')}" for a in available
            )
        else:
            actions_text = "\n".join(f"- {a.value}" for a in available)

        rel_text = "\n".join(
            f"- Agent {aid}: {desc}" for aid, desc in list(agent.relationships.items())[:5]
        ) or "No established relationships yet."

        p = agent.personality
        market_personality = ""
        if is_market:
            market_personality = (
                f"Consumer traits: brand_loyalty={p.brand_loyalty:.1f}, "
                f"price_sensitivity={p.price_sensitivity:.1f}, "
                f"social_proof={p.social_proof:.1f}, "
                f"novelty_seeking={p.novelty_seeking:.1f}"
            )

        market_context = ""
        if is_market:
            m = world_state.metrics
            market_context = (
                f"\nMARKET PULSE:\n"
                f"Brand sentiment: {m.brand_sentiment:.2f}, "
                f"Purchase intent: {m.purchase_intent:.2f}, "
                f"Word of mouth: {m.word_of_mouth:.2f}, "
                f"Churn risk: {m.churn_risk:.2f}, "
                f"Adoption rate: {m.adoption_rate:.2f}"
            )
            position_tracker = self._build_position_tracker(agent, all_agents)
            if position_tracker:
                market_context += position_tracker
            loyalty_anchor = self._loyalty_anchor(agent)
            if loyalty_anchor:
                market_context += "\n" + loyalty_anchor
            stage_nudge = self._decision_stage_nudge(agent)
            if stage_nudge:
                market_context += stage_nudge

        if is_market:
            repetition_warning = self._detect_repetition(agent)
            behavior_rules = BEHAVIOR_RULES_MARKET.format(repetition_warning=repetition_warning)
        else:
            behavior_rules = BEHAVIOR_RULES_SOCIAL

        rules_text = self._build_rules_for_agent(agent, world_state)

        style_key = getattr(agent, "communication_style", "emotional")
        style_desc = COMMUNICATION_STYLES.get(style_key, COMMUNICATION_STYLES["emotional"])
        comm_style_text = f"{style_key} — {style_desc}"

        recent_conversation = self._build_recent_conversation(agent, all_agents)

        context_str = "\n".join(context_parts)
        if agent.life_state is not None:
            life_context_block = build_life_prompt_block(agent, world_state.day, context_str)
        else:
            life_context_block = ""

        system = AGENT_DECISION_SYSTEM.format(
            name=agent.name,
            age=agent.age,
            role=agent.role,
            world_name=world_state.blueprint.name,
            rules=rules_text,
            background=agent.background,
            honesty=agent.personality.honesty,
            ambition=agent.personality.ambition,
            empathy=agent.personality.empathy,
            confrontational=agent.personality.confrontational,
            conformity=agent.personality.conformity,
            market_personality=market_personality,
            communication_style=comm_style_text,
            life_context=life_context_block,
            core_memory="\n".join(f"- {m}" for m in agent.core_memory) or "Nothing significant yet.",
            beliefs="\n".join(f"- {b}" for b in agent.beliefs) or "Still forming opinions.",
            relationships=rel_text,
            working_memory="\n".join(f"- {m}" for m in agent.working_memory[-6:]) or "Just arrived.",
            market_context=market_context,
            recent_conversation=recent_conversation,
            time_of_day=TIMES_OF_DAY[world_state.round_in_day % 3],
            day=world_state.day,
            context=context_str,
            actions=actions_text,
            behavior_rules=behavior_rules,
        )

        return (system, "What do you do?")

    @staticmethod
    def _build_rules_for_agent(agent: AgentPersona, world_state: WorldState) -> str:
        """Filter world rules based on agent's knowledge_level for information diffusion."""
        knowledge = getattr(agent, "knowledge_level", "full")
        all_rules = world_state.blueprint.rules

        if knowledge == "full":
            return "\n".join(f"- {r}" for r in all_rules)

        filtered = []
        change_keywords = ("price", "hike", "increase", "ads", "ad-supported", "password", "sharing", "crack")
        for rule in all_rules:
            rule_lower = rule.lower()
            mentions_change = any(kw in rule_lower for kw in change_keywords)
            if not mentions_change:
                filtered.append(f"- {rule}")
            elif knowledge == "partial":
                filtered.append(f"- (Rumor) You've heard something about changes to pricing or policies, but you're not sure of the details.")
        if knowledge == "unaware":
            filtered.append("- You haven't heard about any recent changes. Everything seems normal to you.")
        return "\n".join(filtered) if filtered else "\n".join(f"- {r}" for r in all_rules)

    @staticmethod
    def _build_recent_conversation(agent: AgentPersona, all_agents: list[AgentPersona]) -> str:
        """Collect recent public speeches from other agents' working memory to create
        conversation threading — agents respond to specific things people said."""
        recent_speeches: list[str] = []
        for other in all_agents:
            if other.id == agent.id:
                continue
            for mem in other.working_memory[-3:]:
                if 'said "' in mem.lower() or "speak_public" in mem.lower():
                    parts = mem.split('said "')
                    if len(parts) >= 2:
                        quote = parts[-1].rstrip('"').rstrip("'")
                        recent_speeches.append(f"- {other.name}: \"{quote[:100]}\"")
        if not recent_speeches:
            return ""
        shown = recent_speeches[-5:]
        return (
            "RECENT CONVERSATION (what people just said):\n"
            + "\n".join(shown)
            + "\n\nYou can respond to any of these directly, change the subject, or ignore them. "
            "If you respond, reference the person BY NAME."
        )

    @staticmethod
    def _conformity_nudge(agent: AgentPersona) -> str:
        if agent.personality.conformity < 0.4:
            return "You are naturally skeptical. Find the flaw in what was said, even if you partly agree."
        if agent.personality.confrontational > 0.7:
            return "You enjoy challenging people. Push back, even if they have a point."
        return ""

    @staticmethod
    def _should_stay_silent(witness: AgentPersona, is_agreement_pile_on: bool) -> bool:
        """Pre-filter: most people stay silent most of the time. Returns True to skip LLM call."""
        silence_prob = 0.35 + (0.25 * (1.0 - witness.personality.confrontational))
        if witness.personality.ambition < 0.3:
            silence_prob += 0.15
        if is_agreement_pile_on and witness.personality.conformity > 0.5:
            silence_prob += 0.2
        if witness.emotional_state in ("calm", "content", "satisfied"):
            silence_prob += 0.1
        return random.random() < min(0.85, silence_prob)

    async def _reactive_micro_round(
        self,
        speech_actions: list[ActionEntry],
        agents: list[AgentPersona],
        world_state: WorldState,
    ) -> list[ReactiveResponse]:
        reactions: list[ReactiveResponse] = []
        agent_map = {a.id: a for a in agents}

        for speech in speech_actions[:5]:
            if speech.action_type == ActionType.SPEAK_PUBLIC:
                speaker = agent_map.get(speech.agent_id)
                if speaker:
                    witnesses = self.gossip.social_neighbors(speaker, agents, count=4)
                else:
                    witnesses = [a for a in agents if a.id != speech.agent_id][:4]
            else:
                witnesses = [agent_map[t] for t in speech.targets if t in agent_map]

            witnesses = witnesses[:4]
            if not witnesses:
                continue

            is_market = self._is_market_simulation(world_state)

            agreement_count = sum(
                1 for r in reactions
                if r.reaction_type == "respond" and r.content
                and any(kw in (r.content or "").lower() for kw in ("agree", "same", "right", "exactly", "yes"))
            )
            is_pile_on = agreement_count >= 2

            prompts = []
            prompt_witnesses = []
            for w in witnesses:
                if self._should_stay_silent(w, is_pile_on):
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="silent", location=w.location,
                    ))
                    continue

                faction_info = f"You belong to {w.faction}." if w.faction else "You don't belong to any faction."
                beliefs = "\n".join(f"- {b}" for b in w.beliefs[:5]) or "Still forming opinions."
                recent_memory = "\n".join(w.working_memory[-3:]) or "Just arrived."
                nudge = self._conformity_nudge(w)
                style_key = getattr(w, "communication_style", "emotional")
                style_desc = COMMUNICATION_STYLES.get(style_key, COMMUNICATION_STYLES["emotional"])
                comm_style = f"{style_key} — {style_desc}"

                if is_market:
                    prompt = (
                        REACTIVE_PROMPT_MARKET.format(
                            name=w.name,
                            role=w.role,
                            world_name=world_state.blueprint.name,
                            mood=w.emotional_state,
                            conformity=w.personality.conformity,
                            confrontational=w.personality.confrontational,
                            empathy=w.personality.empathy,
                            brand_loyalty=w.personality.brand_loyalty,
                            price_sensitivity=w.personality.price_sensitivity,
                            social_proof=w.personality.social_proof,
                            novelty_seeking=w.personality.novelty_seeking,
                            faction_info=faction_info,
                            conformity_nudge=nudge,
                            communication_style=comm_style,
                            beliefs=beliefs,
                            recent_memory=recent_memory,
                            speaker=speech.agent_name,
                            content=speech.speech or "",
                        ),
                        ""
                    )
                else:
                    market_traits = ""
                    prompt = (
                        REACTIVE_PROMPT_SOCIAL.format(
                            name=w.name,
                            role=w.role,
                            world_name=world_state.blueprint.name,
                            mood=w.emotional_state,
                            conformity=w.personality.conformity,
                            confrontational=w.personality.confrontational,
                            empathy=w.personality.empathy,
                            market_traits=market_traits,
                            faction_info=faction_info,
                            conformity_nudge=nudge,
                            communication_style=comm_style,
                            beliefs=beliefs,
                            recent_memory=recent_memory,
                            speaker=speech.agent_name,
                            content=speech.speech or "",
                        ),
                        ""
                    )
                prompts.append(prompt)
                prompt_witnesses.append(w)

            if not prompts:
                continue

            responses = await self.llm.generate_batch(
                [(p[0], p[1] or "React.") for p in prompts],
                json_mode=False,
                max_tokens=150,
            )

            for w, resp in zip(prompt_witnesses, responses):
                resp = resp.strip()
                if not resp:
                    continue

                letter = resp[0].lower()
                content = resp[1:].strip().lstrip(")].,:- ")

                if letter == "a":
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="respond", content=content or None,
                        location=w.location,
                    ))
                elif letter == "b":
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="whisper", content=content or None,
                        location=w.location,
                    ))
                else:
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="silent",
                        location=w.location,
                    ))

        return reactions

    @staticmethod
    def _describe_action_for_reaction(entry: ActionEntry) -> str:
        at = entry.action_type
        args = entry.action_args or {}
        if at == ActionType.PROTEST:
            target = args.get("target", "the current situation")
            speech = f', saying: "{entry.speech}"' if entry.speech else ""
            return f"protest against {target}{speech}"
        elif at == ActionType.ABANDON:
            product = args.get("product", "their position")
            reason = args.get("reason", "")
            speech = f', saying: "{entry.speech}"' if entry.speech else ""
            reason_text = f" because {reason}" if reason else ""
            return f"abandon {product}{reason_text}{speech}"
        elif at == ActionType.DEFECT:
            how = args.get("how", "break the rules")
            speech = f', saying: "{entry.speech}"' if entry.speech else ""
            return f"defect — {how}{speech}"
        elif at == ActionType.RECOMMEND:
            product = args.get("product", "something")
            reason = args.get("reason", "")
            return f'recommend {product}{f" because {reason}" if reason else ""}'
        elif at == ActionType.COMPARE:
            a_name = args.get("product_a", "one option")
            b_name = args.get("product_b", "another")
            return f"start comparing {a_name} and {b_name}"
        elif at == ActionType.PURCHASE:
            product = args.get("product", "something")
            return f"decide to purchase {product}"
        return f"take action: {at.value}"

    async def _reactive_micro_round_actions(
        self,
        action_entries: list[ActionEntry],
        agents: list[AgentPersona],
        world_state: WorldState,
    ) -> list[ReactiveResponse]:
        reactions: list[ReactiveResponse] = []
        agent_map = {a.id: a for a in agents}

        for entry in action_entries[:4]:
            actor = agent_map.get(entry.agent_id)
            if not actor:
                continue

            witnesses = self.gossip.social_neighbors(actor, agents, count=3)
            if not witnesses:
                witnesses = [a for a in agents if a.id != entry.agent_id][:3]
            witnesses = [w for w in witnesses if w.id != entry.agent_id][:3]
            if not witnesses:
                continue

            action_desc = self._describe_action_for_reaction(entry)
            is_market = self._is_market_simulation(world_state)

            prompts = []
            prompt_witnesses = []
            for w in witnesses:
                if self._should_stay_silent(w, False):
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="silent", location=w.location,
                    ))
                    continue

                faction_info = f"You belong to {w.faction}." if w.faction else "You don't belong to any faction."
                beliefs = "\n".join(f"- {b}" for b in w.beliefs[:5]) or "Still forming opinions."
                recent_memory = "\n".join(w.working_memory[-3:]) or "Just arrived."
                nudge = self._conformity_nudge(w)
                style_key = getattr(w, "communication_style", "emotional")
                style_desc = COMMUNICATION_STYLES.get(style_key, COMMUNICATION_STYLES["emotional"])
                comm_style = f"{style_key} — {style_desc}"

                p = w.personality
                market_traits = ""
                if is_market:
                    market_traits = (
                        f"Consumer traits: brand_loyalty={p.brand_loyalty:.1f}, "
                        f"price_sensitivity={p.price_sensitivity:.1f}, "
                        f"social_proof={p.social_proof:.1f}, "
                        f"novelty_seeking={p.novelty_seeking:.1f}"
                    )

                prompt = (
                    REACTIVE_ACTION_PROMPT.format(
                        name=w.name,
                        role=w.role,
                        world_name=world_state.blueprint.name,
                        mood=w.emotional_state,
                        conformity=p.conformity,
                        confrontational=p.confrontational,
                        empathy=p.empathy,
                        market_traits=market_traits,
                        faction_info=faction_info,
                        conformity_nudge=nudge,
                        communication_style=comm_style,
                        beliefs=beliefs,
                        recent_memory=recent_memory,
                        actor=entry.agent_name,
                        action_description=action_desc,
                    ),
                    ""
                )
                prompts.append(prompt)
                prompt_witnesses.append(w)

            if not prompts:
                continue

            responses = await self.llm.generate_batch(
                [(p[0], p[1] or "React.") for p in prompts],
                json_mode=False,
                max_tokens=150,
            )

            for w, resp in zip(prompt_witnesses, responses):
                resp = resp.strip()
                if not resp:
                    continue

                letter = resp[0].lower()
                content = resp[1:].strip().lstrip(")].,:- ")

                if letter == "a":
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="respond", content=content or None,
                        location=w.location,
                    ))
                elif letter == "b":
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="whisper", content=content or None,
                        location=w.location,
                    ))
                else:
                    reactions.append(ReactiveResponse(
                        agent_id=w.id, agent_name=w.name,
                        reaction_type="silent",
                        location=w.location,
                    ))

        return reactions

    async def _fulfill_research(
        self,
        entries: list[ActionEntry],
        agents: list[AgentPersona],
        world_state: WorldState,
    ) -> list[ActionEntry]:
        agent_map = {a.id: a for a in agents}

        research_entries = [e for e in entries if e.action_type == ActionType.RESEARCH]
        investigate_entries = [e for e in entries if e.action_type == ActionType.INVESTIGATE]

        max_searches = self.research.max_per_round if self.research else 5
        capped_research = research_entries[:max_searches]
        overflow_research = research_entries[max_searches:]

        for entry in overflow_research:
            agent = agent_map.get(entry.agent_id)
            if agent:
                query = entry.action_args.get("query", "something")
                agent.working_memory.append(
                    f"Day {world_state.day}: Wanted to research '{query[:40]}' but didn't get to it."
                )
                if len(agent.working_memory) > 9:
                    agent.working_memory = agent.working_memory[-9:]

        search_tasks = []
        search_entries = []
        for entry in capped_research:
            agent = agent_map.get(entry.agent_id)
            if agent:
                query = entry.action_args.get("query", "")
                reason = entry.action_args.get("reason", "")
                search_tasks.append(
                    self.research.search_and_summarize(query, reason, agent, world_state)
                )
                search_entries.append(entry)

        if search_tasks:
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            for entry, result in zip(search_entries, search_results):
                agent = agent_map.get(entry.agent_id)
                if not agent:
                    continue
                if isinstance(result, str) and result:
                    entry.action_args["findings"] = result
                    agent.working_memory.append(
                        f"Day {world_state.day}: Researched '{entry.action_args.get('query', '')}' — {result[:150]}"
                    )
                    if getattr(agent, "knowledge_level", "full") != "full":
                        agent.knowledge_level = "full"
                else:
                    agent.working_memory.append(
                        f"Day {world_state.day}: Tried to research but couldn't find useful information."
                    )
                if len(agent.working_memory) > 9:
                    agent.working_memory = agent.working_memory[-9:]

        investigate_tasks = []
        investigate_pairs = []
        for entry in investigate_entries:
            agent = agent_map.get(entry.agent_id)
            target_id = entry.targets[0] if entry.targets else None
            target = agent_map.get(target_id) if target_id else None
            if agent and target:
                question = entry.action_args.get("question", "")
                investigate_tasks.append(
                    self._run_investigation(agent, target, question, world_state)
                )
                investigate_pairs.append((entry, agent, target))

        if investigate_tasks:
            investigate_results = await asyncio.gather(*investigate_tasks, return_exceptions=True)
            for (entry, agent, target), result in zip(investigate_pairs, investigate_results):
                question = entry.action_args.get("question", "")
                if isinstance(result, str) and result:
                    entry.action_args["response"] = result
                    agent.working_memory.append(
                        f"Day {world_state.day}: Asked {target.name} '{question[:60]}' — they said: '{result[:100]}'"
                    )
                    target.working_memory.append(
                        f"Day {world_state.day}: {agent.name} asked me '{question[:60]}' — I told them: '{result[:80]}'"
                    )
                else:
                    agent.working_memory.append(
                        f"Day {world_state.day}: Tried to talk to {target.name} but couldn't get a clear answer."
                    )
                for a in (agent, target):
                    if len(a.working_memory) > 9:
                        a.working_memory = a.working_memory[-9:]

        return entries

    async def _run_investigation(
        self,
        agent: AgentPersona,
        target: AgentPersona,
        question: str,
        world_state: WorldState,
    ) -> str:
        p = target.personality
        market_traits = ""
        has_market_traits = (
            p.brand_loyalty != 0.5 or p.price_sensitivity != 0.5
            or p.social_proof != 0.5 or p.novelty_seeking != 0.5
        )
        if has_market_traits:
            market_traits = (
                f"Consumer traits: brand_loyalty={p.brand_loyalty:.1f}, "
                f"price_sensitivity={p.price_sensitivity:.1f}, "
                f"social_proof={p.social_proof:.1f}, "
                f"novelty_seeking={p.novelty_seeking:.1f}"
            )

        beliefs = "\n".join(f"- {b}" for b in target.beliefs[:5]) or "Still forming opinions."
        recent_memory = "\n".join(target.working_memory[-3:]) or "Just arrived."

        rel_key = str(agent.id)
        relationship = target.relationships.get(rel_key, "No prior relationship.")

        system = INVESTIGATE_PROMPT.format(
            target_name=target.name,
            target_age=target.age,
            target_role=target.role,
            world_name=world_state.blueprint.name,
            mood=target.emotional_state,
            honesty=p.honesty,
            confrontational=p.confrontational,
            empathy=p.empathy,
            conformity=p.conformity,
            market_traits=market_traits,
            beliefs=beliefs,
            recent_memory=recent_memory,
            agent_name=agent.name,
            question=question,
            relationship=relationship,
        )

        try:
            response = await self.llm.generate(
                system=system,
                user=question,
                json_mode=False,
                max_tokens=150,
            )
            return response.strip()
        except Exception as e:
            logger.warning("Investigation failed (%s -> %s): %s", agent.name, target.name, e)
            return ""

    async def _reflective_memory_pass(
        self, simulation_id: str, agents: list[AgentPersona], world_state: WorldState
    ):
        prompts = []
        for agent in agents:
            system = (
                f"You are {agent.name}, {agent.role} in {world_state.blueprint.name}. "
                f"Reflect on the past 30 days."
            )
            user = (
                f"Your working memory of recent events:\n"
                + "\n".join(f"- {m}" for m in agent.working_memory)
                + f"\n\nYour current core memories:\n"
                + "\n".join(f"- {m}" for m in agent.core_memory)
                + f"\n\nYour current beliefs:\n"
                + "\n".join(f"- {b}" for b in agent.beliefs)
                + "\n\nUpdate your core_memory (max 10 items), beliefs, and goals. "
                "Drop anything no longer relevant. Add anything now important.\n"
                "Return JSON: {\"core_memory\": [...], \"beliefs\": [...], \"goals\": [...]}"
            )
            prompts.append((system, user))

        responses = await self.llm.generate_batch(prompts, json_mode=True, max_tokens=400)

        for agent, resp in zip(agents, responses):
            data = parse_json(resp)
            if data:
                if "core_memory" in data and isinstance(data["core_memory"], list):
                    agent.core_memory = [str(m) for m in data["core_memory"]][:10]
                if "beliefs" in data and isinstance(data["beliefs"], list):
                    agent.beliefs = [str(b) for b in data["beliefs"]][:10]
                if "goals" in data and isinstance(data["goals"], list):
                    agent.goals = [str(g) for g in data["goals"]][:5]

    @staticmethod
    def _count_significant(actions: list[ActionEntry]) -> int:
        significant_types = {
            ActionType.PROTEST, ActionType.DEFECT, ActionType.PROPOSE_RULE,
            ActionType.FORM_GROUP, ActionType.VOTE, ActionType.BUILD,
            ActionType.PURCHASE, ActionType.ABANDON, ActionType.RECOMMEND,
            ActionType.RESEARCH, ActionType.INVESTIGATE,
        }
        return sum(1 for a in actions if a.action_type in significant_types)

    async def pause(self, simulation_id: str) -> bool:
        if simulation_id in self._paused:
            self._paused[simulation_id].clear()
            return True
        return False

    async def resume(self, simulation_id: str) -> bool:
        if simulation_id in self._paused:
            self._paused[simulation_id].set()
            return True
        return False

    async def stop(self, simulation_id: str) -> bool:
        if simulation_id not in self._running:
            return False
        self._running[simulation_id] = False
        if simulation_id in self._paused:
            self._paused[simulation_id].set()
        return True

    async def set_speed(self, simulation_id: str, mode: SpeedMode):
        self._speed[simulation_id] = mode

    async def inject_event(
        self, simulation_id: str, event_text: str, world_state: WorldState, agents: list[AgentPersona]
    ) -> str:
        system = (
            f"An event is injected into {world_state.blueprint.name}: \"{event_text}\"\n"
            f"Rules: {'; '.join(world_state.blueprint.rules)}\n"
            "Describe: 1) What physically happens 2) Resource changes if any.\n"
            "Return JSON: {\"description\": \"...\", \"resource_changes\": {}}"
        )
        response = await self.llm.generate(system=system, user=event_text, json_mode=True, max_tokens=300)
        data = parse_json(response)

        description = data.get("description", event_text)

        self.gossip.inject_event_via_gossip(
            sim_id=simulation_id,
            event_desc=description,
            agents=agents,
            round_num=-1,
            day=world_state.day,
        )

        world_state.active_disputes.append(f"Event: {description[:80]}")
        if len(world_state.active_disputes) > 10:
            world_state.active_disputes = world_state.active_disputes[-10:]
        world_state.metrics.stability = max(0.0, world_state.metrics.stability - 0.1)
        world_state.metrics.conflict = min(1.0, world_state.metrics.conflict + 0.1)

        await self.store.save_world_state(simulation_id, -1, world_state)
        await self.store.save_agents_batch(simulation_id, agents)

        return description

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
