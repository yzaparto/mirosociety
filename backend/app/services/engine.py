from __future__ import annotations
import asyncio
import logging
import random
from typing import Callable, Awaitable, Any

from app.models.agent import AgentPersona
from app.models.action import ActionType, AgentDecision, ActionEntry, ReactiveResponse
from app.models.world import WorldState, WorldMetrics
from app.models.simulation import SimulationStatus, SpeedMode, SSEEvent
from app.db.store import SimulationStore
from app.services.llm import LLMClient, parse_json
from app.services.tension import TensionEngine
from app.services.resolver import ActionResolver
from app.services.narrator import Narrator
from app.services.research import ResearchService
from app.constants import TIMES_OF_DAY

logger = logging.getLogger(__name__)

AGENT_DECISION_SYSTEM = """You are {name}, a {age}-year-old {role} in {world_name}.

THE RULES OF THIS WORLD:
{rules}

WHO YOU ARE:
{background}
Personality: honesty={honesty:.1f}, ambition={ambition:.1f}, empathy={empathy:.1f}, confrontational={confrontational:.1f}, conformity={conformity:.1f}
{market_personality}

WHAT YOU KNOW TO BE TRUE (core memories):
{core_memory}

WHAT YOU BELIEVE RIGHT NOW:
{beliefs}

YOUR RELATIONSHIPS:
{relationships}

WHAT JUST HAPPENED (recent days):
{working_memory}
{market_context}

THE SITUATION RIGHT NOW:
It is {time_of_day} on day {day}.
{context}

AVAILABLE ACTIONS (pick exactly one):
{actions}

{behavior_rules}

Think step by step:
1. FEEL: What is your emotional reaction to the current situation?
2. WANT: Given your personality and goals, what do you want right now?
3. FEAR: What could go wrong? What worries you?
4. DECIDE: What action do you take?

Respond as JSON:
{{
  "feel": "one sentence emotional reaction",
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
- You are a CONSUMER, not a debater. Your actions should reflect real consumer behavior.
- Do NOT repeat things you've already said. Check your working memory. If you've already stated your position on the topic, DO SOMETHING DIFFERENT — buy, abandon, recommend, compare, protest, or observe.
- CRITICAL: After day 1, you MUST stop just talking and start ACTING. Real consumers don't debate endlessly — they make purchase decisions, switch brands, recommend to friends, or compare alternatives.
- Use PURCHASE when you decide to buy or commit to the product/brand.
- Use ABANDON when you decide to leave, cancel, or switch away. State your real reason.
- Use RECOMMEND when you want to influence a specific person to try or avoid something.
- Use COMPARE when you want to evaluate alternatives publicly.
- Use PROTEST when you are genuinely unhappy and want to make noise about it.
- Use DEFECT when you decide to actively switch to a competitor.
- SPEAK_PUBLIC is for sharing genuine opinions, reviews, or reactions — not for abstract philosophical debate.
- If an EVENT happens, it should change your BEHAVIOR, not just your talking points. Ask yourself: does this make me more or less likely to buy? To leave? To recommend?
- Your brand_loyalty, price_sensitivity, social_proof, and novelty_seeking traits should guide your decisions:
  * High brand_loyalty → you resist change, COMPLY, defend the brand
  * High price_sensitivity → you COMPARE prices, consider ABANDON if value drops
  * High social_proof → you follow what others are doing (if they PURCHASE, you consider it; if they ABANDON, you waver)
  * High novelty_seeking → you're excited by change, early to PURCHASE new things
- Before forming strong opinions, consider whether you actually KNOW the facts or are just assuming. If you're uncertain, RESEARCH to find real information or INVESTIGATE someone who might know.
- If someone makes a claim you doubt, you can INVESTIGATE them directly or RESEARCH the claim.
{repetition_warning}"""

REACTIVE_PROMPT_SOCIAL = """You are {name}, a {role} in {world_name}.
Your mood: {mood}.
Personality: conformity={conformity:.1f}, confrontational={confrontational:.1f}, empathy={empathy:.1f}
{market_traits}
{faction_info}

YOUR BELIEFS:
{beliefs}

YOUR RECENT EXPERIENCE:
{recent_memory}

You just heard {speaker} say: "{content}"

How do you react? React based on YOUR beliefs and personality, not to be polite.
Disagreement, skepticism, sarcasm, deflection, and changing the subject are all valid.
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

YOUR BELIEFS:
{beliefs}

YOUR RECENT EXPERIENCE:
{recent_memory}

You just heard {speaker} say: "{content}"

React as a REAL CONSUMER, not a debate partner. Consider:
- Does this make you more or less likely to buy/stay/leave?
- Would you tell a friend about this? Would you warn them?
- Are you annoyed, excited, indifferent, or worried?

Be specific and personal. Reference your own experience with the product/brand.
Don't give generic "balance" takes — say what you'd actually say as a customer.

(a) Respond publicly — say something everyone can hear
(b) Whisper privately — say something only to someone near you
(c) Stay silent — keep your thoughts to yourself

Reply with ONLY the letter and your response (1-2 sentences max).
Examples: "a I already cancelled my order — this new logo looks like a toy brand." or "b Honestly? I'm looking at Rivian now." or "c" """


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
    ):
        self.llm = llm
        self.store = store
        self.tension = tension
        self.resolver = resolver
        self.narrator = narrator
        self.research = research
        self._running: dict[str, bool] = {}
        self._paused: dict[str, asyncio.Event] = {}
        self._speed: dict[str, SpeedMode] = {}
        self._total_actions: dict[str, int] = {}
        self._last_narrative: dict[str, str] = {}

    async def _wait_if_paused(self, simulation_id: str) -> bool:
        """Block while paused. Returns False if the simulation was stopped."""
        if simulation_id not in self._paused:
            return False
        await self._paused[simulation_id].wait()
        return self._running.get(simulation_id, False)

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

        total_rounds = world_state.blueprint.time_config.total_days * world_state.blueprint.time_config.rounds_per_day
        round_num = start_round

        await self.store.save_world_state(simulation_id, round_num, world_state)
        await self.store.save_agents_batch(simulation_id, agents)

        try:
            while round_num < total_rounds and self._running.get(simulation_id, False):
                if not await self._wait_if_paused(simulation_id):
                    break

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

                reactions: list[ReactiveResponse] = []
                if speech_actions:
                    reactions = await self._reactive_micro_round(speech_actions, agents, world_state)

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

                is_market_sim = self._is_market_simulation(world_state)
                market_action_types = {
                    ActionType.PURCHASE, ActionType.ABANDON, ActionType.RECOMMEND,
                    ActionType.COMPARE, ActionType.PROTEST, ActionType.DEFECT, ActionType.COMPLY,
                }

                for agent in agents:
                    tod = TIMES_OF_DAY[world_state.round_in_day % 3]
                    summary = f"Day {world_state.day} {tod}: "
                    my_actions = [e for e in resolved_entries if e.agent_id == agent.id]
                    if my_actions:
                        parts = []
                        for e in my_actions:
                            part = e.action_type.value
                            if e.speech:
                                part += f': said "{e.speech[:80]}"'
                            if e.action_type == ActionType.PURCHASE:
                                part += f': bought {e.action_args.get("product", "the product")}'
                            elif e.action_type == ActionType.ABANDON:
                                part += f': left {e.action_args.get("product", "the product")} — {e.action_args.get("reason", "")[:60]}'
                            elif e.action_type == ActionType.RECOMMEND:
                                part += f': recommended {e.action_args.get("product", "the product")}'
                            elif e.action_type == ActionType.COMPARE:
                                part += f': compared {e.action_args.get("product_a", "")} vs {e.action_args.get("product_b", "")}'
                            elif e.action_type == ActionType.RESEARCH:
                                findings = e.action_args.get("findings", "")
                                part += f': searched \'{e.action_args.get("query", "")}\''
                                if findings:
                                    part += f' — {findings[:120]}'
                            elif e.action_type == ActionType.INVESTIGATE:
                                response = e.action_args.get("response", "")
                                target_names = [a.name for a in agents if a.id in e.targets]
                                target_name = target_names[0] if target_names else "someone"
                                part += f': asked {target_name} \'{e.action_args.get("question", "")[:50]}\''
                                if response:
                                    part += f' — they said: \'{response[:80]}\''
                            if e.targets:
                                target_names = [a.name for a in agents if a.id in e.targets]
                                if target_names:
                                    part += f" (to {', '.join(target_names)})"
                            parts.append(part)
                        summary += "; ".join(parts)
                    else:
                        notable = [e for e in resolved_entries if e.agent_id != agent.id]
                        if notable:
                            heard = []
                            for e in notable[:6]:
                                if is_market_sim and e.action_type in market_action_types:
                                    if e.action_type == ActionType.PURCHASE:
                                        heard.append(f"{e.agent_name} BOUGHT {e.action_args.get('product', 'the product')}")
                                    elif e.action_type == ActionType.ABANDON:
                                        heard.append(f"{e.agent_name} LEFT {e.action_args.get('product', 'the product')}")
                                    elif e.action_type == ActionType.RECOMMEND:
                                        heard.append(f"{e.agent_name} RECOMMENDED {e.action_args.get('product', 'the product')}")
                                    elif e.action_type == ActionType.COMPARE:
                                        heard.append(f"{e.agent_name} COMPARED {e.action_args.get('product_a', '')} vs {e.action_args.get('product_b', '')}")
                                    elif e.action_type == ActionType.PROTEST:
                                        heard.append(f"{e.agent_name} PROTESTED: {e.action_args.get('target', '')[:60]}")
                                    elif e.action_type == ActionType.DEFECT:
                                        heard.append(f"{e.agent_name} SWITCHED to a competitor")
                                    else:
                                        heard.append(f"{e.agent_name} did {e.action_type.value}")
                                elif e.action_type == ActionType.RESEARCH:
                                    heard.append(f"{e.agent_name} was looking something up online: '{e.action_args.get('query', '')[:50]}'")
                                elif e.action_type == ActionType.INVESTIGATE:
                                    target_names = [a.name for a in agents if a.id in e.targets]
                                    target_name = target_names[0] if target_names else "someone"
                                    heard.append(f"{e.agent_name} went to question {target_name} directly")
                                elif e.speech:
                                    heard.append(f'{e.agent_name} said: "{e.speech[:120]}"')
                                elif e.action_type in (ActionType.PROTEST, ActionType.DEFECT, ActionType.FORM_GROUP, ActionType.ABANDON, ActionType.PURCHASE):
                                    heard.append(f"{e.agent_name} did {e.action_type.value}")
                            if reactions:
                                for r in reactions[:4]:
                                    if r.content and r.reaction_type != "silent":
                                        heard.append(f'{r.agent_name} reacted: "{r.content[:100]}"')
                            summary += "Heard nearby: " + "; ".join(heard) if heard else "A quiet period."
                        else:
                            summary += "A quiet period."

                    agent.working_memory.append(summary)
                    if len(agent.working_memory) > 9:
                        agent.working_memory = agent.working_memory[-9:]

                if tension_event:
                    for agent in agents:
                        agent.working_memory.append(f"Day {world_state.day}: EVENT — {tension_event[:100]}")

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
                             "goals": a.goals}
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
        finally:
            self._running.pop(simulation_id, None)
            self._paused.pop(simulation_id, None)
            self._speed.pop(simulation_id, None)
            self._total_actions.pop(simulation_id, None)
            self._last_narrative.pop(simulation_id, None)
            self.tension.cleanup(simulation_id)

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
        speech_memories = [
            m for m in agent.working_memory
            if "said" in m.lower() or "speak_public" in m.lower()
        ]
        if len(speech_memories) >= 3:
            return (
                "\n⚠️ WARNING: You have spoken publicly multiple times already. "
                "You MUST take a NON-SPEECH action this turn. Choose from: "
                "PURCHASE, ABANDON, RECOMMEND, COMPARE, PROTEST, DEFECT, COMPLY, or OBSERVE. "
                "No more talking — ACT on your beliefs."
            )
        if len(speech_memories) >= 2:
            return (
                "\n⚠️ You've already shared your opinion. Consider taking concrete action instead of speaking again. "
                "What would you actually DO as a consumer — buy, leave, recommend, compare, or protest?"
            )
        return ""

    @staticmethod
    def _build_position_tracker(agent: AgentPersona, all_agents: list[AgentPersona]) -> str:
        positions = []
        for other in all_agents:
            if other.id == agent.id:
                continue
            recent_speech = [
                m for m in other.working_memory
                if "said" in m.lower()
            ]
            recent_actions = [
                m for m in other.working_memory
                if any(act in m.lower() for act in ("purchase", "abandon", "recommend", "protest", "defect"))
            ]
            if recent_actions:
                positions.append(f"- {other.name} ({other.emotional_state}): {recent_actions[-1]}")
            elif recent_speech:
                positions.append(f"- {other.name} ({other.emotional_state}): still just talking")
        if positions:
            return "\nWHAT OTHERS ARE DOING (not just saying):\n" + "\n".join(positions[:5])
        return ""

    def _build_decision_prompt(
        self,
        agent: AgentPersona,
        world_state: WorldState,
        all_agents: list[AgentPersona],
    ) -> tuple[str, str]:
        others = [a for a in all_agents if a.id != agent.id]
        nearby = random.sample(others, min(8, len(others)))
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

        if is_market:
            repetition_warning = self._detect_repetition(agent)
            behavior_rules = BEHAVIOR_RULES_MARKET.format(repetition_warning=repetition_warning)
        else:
            behavior_rules = BEHAVIOR_RULES_SOCIAL

        system = AGENT_DECISION_SYSTEM.format(
            name=agent.name,
            age=agent.age,
            role=agent.role,
            world_name=world_state.blueprint.name,
            rules="\n".join(f"- {r}" for r in world_state.blueprint.rules),
            background=agent.background,
            honesty=agent.personality.honesty,
            ambition=agent.personality.ambition,
            empathy=agent.personality.empathy,
            confrontational=agent.personality.confrontational,
            conformity=agent.personality.conformity,
            market_personality=market_personality,
            core_memory="\n".join(f"- {m}" for m in agent.core_memory) or "Nothing significant yet.",
            beliefs="\n".join(f"- {b}" for b in agent.beliefs) or "Still forming opinions.",
            relationships=rel_text,
            working_memory="\n".join(f"- {m}" for m in agent.working_memory[-6:]) or "Just arrived.",
            market_context=market_context,
            time_of_day=TIMES_OF_DAY[world_state.round_in_day % 3],
            day=world_state.day,
            context="\n".join(context_parts),
            actions=actions_text,
            behavior_rules=behavior_rules,
        )

        return (system, "What do you do?")

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
                witnesses = [
                    a for a in agents
                    if a.id != speech.agent_id
                ]
            else:
                witnesses = [agent_map[t] for t in speech.targets if t in agent_map]

            witnesses = witnesses[:6]
            if not witnesses:
                continue

            is_market = self._is_market_simulation(world_state)

            prompts = []
            for w in witnesses:
                faction_info = f"You belong to {w.faction}." if w.faction else "You don't belong to any faction."
                beliefs = "\n".join(f"- {b}" for b in w.beliefs[:5]) or "Still forming opinions."
                recent_memory = "\n".join(w.working_memory[-3:]) or "Just arrived."

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
                            beliefs=beliefs,
                            recent_memory=recent_memory,
                            speaker=speech.agent_name,
                            content=speech.speech or "",
                        ),
                        ""
                    )
                prompts.append(prompt)

            responses = await self.llm.generate_batch(
                [(p[0], p[1] or "React.") for p in prompts],
                json_mode=False,
                max_tokens=150,
            )

            for w, resp in zip(witnesses, responses):
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

        for agent in agents:
            agent.working_memory.append(f"Day {world_state.day}: INJECTED EVENT — {description[:100]}")

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
