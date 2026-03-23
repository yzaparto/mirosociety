from __future__ import annotations
import logging
import random
import uuid

from app.models.agent import AgentPersona, SocialEdge
from app.models.action import ActionType, AgentDecision, ActionEntry
from app.models.world import WorldState, WorldMetrics, Institution, Proposal
from app.constants import TIMES_OF_DAY, normalize_emotional_state

logger = logging.getLogger(__name__)


class ActionResolver:
    @staticmethod
    def _resolve_agent_id(ref, agent_map: dict[int, AgentPersona]) -> int | None:
        if ref is None:
            return None
        try:
            aid = int(ref)
            if aid in agent_map:
                return aid
        except (ValueError, TypeError):
            pass
        ref_str = str(ref).strip().lower()
        for a in agent_map.values():
            if a.name.lower() == ref_str:
                return a.id
        return None

    @staticmethod
    def _update_relationship(agent: AgentPersona, target_id: int, description: str):
        key = str(target_id)
        existing = agent.relationships.get(key, "")
        if existing:
            parts = existing.split(" | ")
            if description not in parts:
                parts.append(description)
                if len(parts) > 4:
                    parts = parts[-4:]
                agent.relationships[key] = " | ".join(parts)
        else:
            agent.relationships[key] = description

    @staticmethod
    def _strengthen_social_edge(
        agent: AgentPersona,
        target_id: int,
        strength_delta: float = 0.05,
        sentiment_delta: float = 0.0,
    ):
        for edge in agent.social_connections:
            if edge.target_id == target_id:
                edge.strength = min(1.0, max(0.0, edge.strength + strength_delta))
                edge.sentiment = min(1.0, max(-1.0, edge.sentiment + sentiment_delta))
                return
        agent.social_connections.append(SocialEdge(
            target_id=target_id,
            strength=min(1.0, max(0.0, 0.3 + strength_delta)),
            sentiment=min(1.0, max(-1.0, sentiment_delta)),
        ))

    def resolve(
        self,
        decisions: list[tuple[AgentPersona, AgentDecision]],
        world_state: WorldState,
        all_agents: list[AgentPersona],
        round_num: int,
        forecast=None,
    ) -> tuple[list[ActionEntry], WorldState, list[AgentPersona]]:
        entries: list[ActionEntry] = []
        agent_map = {a.id: a for a in all_agents}
        time_of_day = TIMES_OF_DAY[world_state.round_in_day % 3]

        sorted_decisions = sorted(
            decisions,
            key=lambda d: d[0].resources.get("influence", 0),
            reverse=True,
        )

        for agent, decision in sorted_decisions:
            entry = self._process_decision(
                agent, decision, world_state, agent_map, round_num, time_of_day
            )
            entries.append(entry)

            if decision.belief_updates:
                current = agent_map[agent.id]
                for belief in decision.belief_updates:
                    if belief and belief not in current.beliefs:
                        current.beliefs.append(belief)
                        if len(current.beliefs) > 10:
                            current.beliefs.pop(0)

            if decision.memory_promotion:
                current = agent_map[agent.id]
                promo = decision.memory_promotion
                if promo not in current.core_memory:
                    current.core_memory.append(promo)
                    if len(current.core_memory) > 10:
                        current.core_memory.pop(0)

            agent_map[agent.id].emotional_state = normalize_emotional_state(decision.feel)

        old_metrics = world_state.metrics.model_copy()
        world_state.metrics = self._update_metrics(world_state.metrics, entries, world_state)

        if forecast is not None:
            try:
                proposed = world_state.metrics.model_dump()
                current = old_metrics.model_dump()
                sim_id = getattr(forecast, '_current_sim_id', '')
                clamped = forecast.clamp_metrics(sim_id, proposed, current)
                for key, val in clamped.items():
                    if hasattr(world_state.metrics, key):
                        setattr(world_state.metrics, key, val)
            except Exception:
                pass

        all_agents = list(agent_map.values())
        self._emotional_contagion(all_agents)
        self._emotional_decay(all_agents)

        return entries, world_state, all_agents

    def _process_decision(
        self,
        agent: AgentPersona,
        decision: AgentDecision,
        world_state: WorldState,
        agent_map: dict[int, AgentPersona],
        round_num: int,
        time_of_day: str,
    ) -> ActionEntry:
        action_args = dict(decision.args)
        targets: list[int] = []
        world_changes: dict = {}
        rel_changes: dict = {}

        at = decision.action

        if at == ActionType.ABANDON:
            product = (decision.args or {}).get("product", "the product").lower()
            if product in agent.abandoned_products:
                at = ActionType.SPEAK_PUBLIC
                decision = AgentDecision(
                    feel=decision.feel, want=decision.want, fear=decision.fear,
                    life_context=decision.life_context, past_echo=decision.past_echo,
                    action=ActionType.SPEAK_PUBLIC, args={},
                    speech=decision.speech or f"I already left {product}.",
                    internal_thought=decision.internal_thought,
                    belief_updates=decision.belief_updates,
                    memory_promotion=decision.memory_promotion,
                )

        if at == ActionType.DEFECT and agent.has_defected:
            at = ActionType.SPEAK_PUBLIC
            decision = AgentDecision(
                feel=decision.feel, want=decision.want, fear=decision.fear,
                life_context=decision.life_context, past_echo=decision.past_echo,
                action=ActionType.SPEAK_PUBLIC, args={},
                speech=decision.speech or "I've already made my switch.",
                internal_thought=decision.internal_thought,
                belief_updates=decision.belief_updates,
                memory_promotion=decision.memory_promotion,
            )

        if at == ActionType.SPEAK_PUBLIC:
            if decision.speech:
                action_args["content"] = decision.speech
            listeners = [
                a for a in agent_map.values()
                if a.id != agent.id and a.location == agent.location
            ]
            if not listeners:
                listeners = [a for a in agent_map.values() if a.id != agent.id]
            for listener in listeners:
                self._strengthen_social_edge(agent, listener.id, 0.03, 0.01)
                self._strengthen_social_edge(listener, agent.id, 0.03, 0.01)

        elif at == ActionType.SPEAK_PRIVATE:
            raw_target = action_args.get("target_id")
            target_id = self._resolve_agent_id(raw_target, agent_map)
            if target_id is not None and target_id in agent_map:
                targets = [target_id]
                action_args["target_id"] = target_id
                if decision.speech:
                    action_args["content"] = decision.speech
                rel_changes[str(target_id)] = "private_conversation"
                self._update_relationship(agent, target_id, "private_conversation")
                self._strengthen_social_edge(agent, target_id, 0.05, 0.02)
                self._strengthen_social_edge(agent_map[target_id], agent.id, 0.05, 0.02)

        elif at == ActionType.TRADE:
            raw_target = action_args.get("target_id")
            target_id = self._resolve_agent_id(raw_target, agent_map)
            give_resource = action_args.get("give_resource", "")
            try:
                give_amount = int(action_args.get("give_amount", 0))
            except (ValueError, TypeError):
                give_amount = 0
            receive_resource = action_args.get("receive_resource", "")
            try:
                receive_amount = int(action_args.get("receive_amount", 0))
            except (ValueError, TypeError):
                receive_amount = 0

            if target_id is not None and target_id in agent_map:
                target = agent_map[target_id]
                if (
                    agent.resources.get(give_resource, 0) >= give_amount
                    and target.resources.get(receive_resource, 0) >= receive_amount
                ):
                    agent.resources[give_resource] = agent.resources.get(give_resource, 0) - give_amount
                    agent.resources[receive_resource] = agent.resources.get(receive_resource, 0) + receive_amount
                    target.resources[give_resource] = target.resources.get(give_resource, 0) + give_amount
                    target.resources[receive_resource] = target.resources.get(receive_resource, 0) - receive_amount
                    targets = [target_id]
                    world_changes["trade"] = True
                    self._update_relationship(agent, target_id, f"Trade partner — exchanged {give_resource} for {receive_resource}")
                    self._update_relationship(target, agent.id, f"Trade partner — exchanged {receive_resource} for {give_resource}")
                    self._strengthen_social_edge(agent, target_id, 0.08, 0.05)
                    self._strengthen_social_edge(target, agent.id, 0.08, 0.05)
                    rel_changes[str(target_id)] = "trade_partner"

        elif at == ActionType.FORM_GROUP:
            group_name = action_args.get("name", "Unnamed Group")
            purpose = action_args.get("purpose", "")
            existing = next((i for i in world_state.institutions if i.name == group_name), None)

            if not existing and len(world_state.institutions) >= 3:
                name_lower = group_name.lower()
                purpose_lower = purpose.lower()
                for inst in world_state.institutions:
                    if (inst.name.lower() in name_lower or name_lower in inst.name.lower()
                            or (purpose_lower and inst.purpose and
                                any(w in inst.purpose.lower() for w in purpose_lower.split() if len(w) > 3))):
                        existing = inst
                        group_name = inst.name
                        break

            if not existing and len(world_state.institutions) >= 8:
                smallest = min(world_state.institutions, key=lambda i: len(i.member_ids))
                existing = smallest
                group_name = smallest.name

            if existing:
                if agent.id not in existing.member_ids:
                    existing.member_ids.append(agent.id)
                agent.faction = group_name
                for mid in existing.member_ids:
                    if mid != agent.id:
                        self._update_relationship(agent_map[mid], agent.id, f"Fellow member of {group_name}")
                        self._update_relationship(agent, mid, f"Fellow member of {group_name}")
                        self._strengthen_social_edge(agent, mid, 0.1, 0.08)
                        self._strengthen_social_edge(agent_map[mid], agent.id, 0.1, 0.08)
                        rel_changes[str(mid)] = "faction_ally"
            else:
                inst = Institution(
                    name=group_name,
                    purpose=purpose,
                    founder_id=agent.id,
                    member_ids=[agent.id],
                    created_day=world_state.day,
                )
                world_state.institutions.append(inst)
                agent.faction = group_name
                world_changes["institution_created"] = group_name
                world_state.metrics.word_of_mouth = min(1.0, world_state.metrics.word_of_mouth + 0.03)
                world_state.metrics.trust += 0.01

        elif at == ActionType.PROPOSE_RULE:
            content = action_args.get("content", decision.speech or "")
            if content:
                proposal = Proposal(
                    id=str(uuid.uuid4())[:8],
                    proposer_id=agent.id,
                    content=content,
                    votes_for=[agent.id],
                    created_round=round_num,
                )
                world_state.proposals.append(proposal)
                world_changes["proposal_created"] = content

        elif at == ActionType.VOTE:
            proposal_id = action_args.get("proposal_id")
            vote = action_args.get("vote", "for")
            if proposal_id:
                for p in world_state.proposals:
                    if p.id == proposal_id and p.status == "open":
                        if vote == "for" and agent.id not in p.votes_for:
                            p.votes_for.append(agent.id)
                        elif vote == "against" and agent.id not in p.votes_against:
                            p.votes_against.append(agent.id)

                        total_votes = len(p.votes_for) + len(p.votes_against)
                        total_agents = len(agent_map)
                        if total_votes >= total_agents * 0.5:
                            if len(p.votes_for) > len(p.votes_against):
                                p.status = "passed"
                                world_state.community_rules.append(p.content)
                                world_changes["rule_passed"] = p.content
                            else:
                                p.status = "rejected"
                                world_changes["rule_rejected"] = p.content
                        break
            else:
                open_proposals = [p for p in world_state.proposals if p.status == "open"]
                if open_proposals:
                    p = open_proposals[0]
                    vote = action_args.get("vote", "for")
                    if vote == "for" and agent.id not in p.votes_for:
                        p.votes_for.append(agent.id)
                    elif vote == "against" and agent.id not in p.votes_against:
                        p.votes_against.append(agent.id)

                    total_votes = len(p.votes_for) + len(p.votes_against)
                    total_agents = len(agent_map)
                    if total_votes >= total_agents * 0.5:
                        if len(p.votes_for) > len(p.votes_against):
                            p.status = "passed"
                            world_state.community_rules.append(p.content)
                            world_changes["rule_passed"] = p.content
                        else:
                            p.status = "rejected"
                            world_changes["rule_rejected"] = p.content

        elif at == ActionType.PROTEST:
            target_rule = action_args.get("target", "the current order")
            world_state.active_disputes.append(f"{agent.name} protests: {target_rule}")
            if len(world_state.active_disputes) > 10:
                world_state.active_disputes.pop(0)

        elif at == ActionType.COMPLY:
            pass

        elif at == ActionType.DEFECT:
            world_state.active_disputes.append(f"{agent.name} defected: {action_args.get('how', 'broke the rules')}")
            if len(world_state.active_disputes) > 10:
                world_state.active_disputes.pop(0)
            agent.has_defected = True
            agent.resources["influence"] = agent.resources.get("influence", 0) + 5
            for other in agent_map.values():
                if other.id != agent.id:
                    if other.personality.conformity > 0.6:
                        self._update_relationship(other, agent.id, f"Saw {agent.name} defy the rules — lost respect")
                        self._strengthen_social_edge(other, agent.id, 0.03, -0.15)
                        rel_changes[str(other.id)] = "lost_respect"
                    elif other.personality.confrontational > 0.6:
                        self._update_relationship(other, agent.id, f"Saw {agent.name} defy the rules — impressed")
                        self._strengthen_social_edge(other, agent.id, 0.05, 0.1)
                        rel_changes[str(other.id)] = "impressed"

        elif at == ActionType.BUILD:
            cost_resource = action_args.get("resource", "goods")
            try:
                cost_amount = int(action_args.get("cost", 20))
            except (ValueError, TypeError):
                cost_amount = 20
            if agent.resources.get(cost_resource, 0) >= cost_amount:
                agent.resources[cost_resource] -= cost_amount
                world_changes["built"] = action_args.get("what", "something")

        elif at == ActionType.OBSERVE:
            agent.resources["knowledge"] = agent.resources.get("knowledge", 0) + 3
            nearby = [a for a in agent_map.values() if a.id != agent.id]
            if nearby:
                scene_parts = []
                for nb in nearby[:5]:
                    scene_parts.append(f"{nb.name} ({nb.emotional_state})")
                agent.working_memory.append(f"Observed: {', '.join(scene_parts)}")
                if len(agent.working_memory) > 9:
                    agent.working_memory = agent.working_memory[-9:]

        elif at == ActionType.RECOMMEND:
            raw_target = action_args.get("target_id")
            target_id = self._resolve_agent_id(raw_target, agent_map)
            product = action_args.get("product", "the product")
            reason = action_args.get("reason", "")
            if target_id is not None and target_id in agent_map:
                target = agent_map[target_id]
                targets = [target_id]
                action_args["target_id"] = target_id
                target.working_memory.append(
                    f"{agent.name} recommended {product}: \"{reason[:80]}\""
                )
                if len(target.working_memory) > 9:
                    target.working_memory = target.working_memory[-9:]
                self._update_relationship(agent, target_id, f"Recommended {product} to them")
                self._strengthen_social_edge(agent, target_id, 0.06, 0.04)
                self._strengthen_social_edge(target, agent.id, 0.06, 0.04)
                rel_changes[str(target_id)] = "recommendation"
                world_changes["recommendation"] = product

        elif at == ActionType.PURCHASE:
            product = action_args.get("product", "the product")
            try:
                amount = int(action_args.get("amount", 0))
            except (ValueError, TypeError):
                amount = 0
            if amount <= 0:
                amount = 10
            cost_resource = "money" if "money" in agent.resources else "goods"
            if agent.resources.get(cost_resource, 0) >= amount:
                agent.resources[cost_resource] -= amount
                world_changes["purchase"] = product
            else:
                world_changes["purchase"] = product

        elif at == ActionType.ABANDON:
            product = action_args.get("product", "the product")
            reason = action_args.get("reason", "")
            world_state.active_disputes.append(f"{agent.name} abandoned {product}: {reason[:60]}")
            if len(world_state.active_disputes) > 10:
                world_state.active_disputes.pop(0)
            world_changes["abandon"] = product
            agent.abandoned_products.add(product.lower())
            if decision.speech:
                action_args["content"] = decision.speech

        elif at == ActionType.COMPARE:
            product_a = action_args.get("product_a", "")
            product_b = action_args.get("product_b", "")
            verdict = action_args.get("verdict", "")
            world_changes["comparison"] = f"{product_a} vs {product_b}"
            others = [a for a in agent_map.values() if a.id != agent.id][:6]
            for other in others:
                other.working_memory.append(
                    f"{agent.name} compared {product_a} vs {product_b}: \"{verdict[:60]}\""
                )
                if len(other.working_memory) > 9:
                    other.working_memory = other.working_memory[-9:]

        elif at == ActionType.RESEARCH:
            agent.resources["knowledge"] = agent.resources.get("knowledge", 0) + 3
            world_changes["research_query"] = action_args.get("query", "")

        elif at == ActionType.INVESTIGATE:
            raw_target = action_args.get("target_id")
            target_id = self._resolve_agent_id(raw_target, agent_map)
            if target_id is not None and target_id in agent_map:
                targets = [target_id]
                action_args["target_id"] = target_id
                agent.resources["knowledge"] = agent.resources.get("knowledge", 0) + 2
                self._update_relationship(agent, target_id, f"Investigated — asked about '{action_args.get('question', '')[:40]}'")
                self._update_relationship(agent_map[target_id], agent.id, f"Was questioned by {agent.name}")
                self._strengthen_social_edge(agent, target_id, 0.04, 0.0)
                self._strengthen_social_edge(agent_map[target_id], agent.id, 0.04, 0.0)
                rel_changes[str(target_id)] = "investigated"

        return ActionEntry(
            round=round_num,
            day=world_state.day,
            time_of_day=time_of_day,
            agent_id=agent.id,
            agent_name=agent.name,
            location=agent.location,
            action_type=at,
            action_args=action_args,
            speech=decision.speech,
            internal_thought=decision.internal_thought,
            targets=targets,
            world_state_changes=world_changes,
            relationship_changes=rel_changes,
        )

    def _update_metrics(
        self,
        old: WorldMetrics,
        actions: list[ActionEntry],
        world_state: WorldState,
    ) -> WorldMetrics:
        alpha = 0.3
        d_stability = 0.0
        d_prosperity = 0.0
        d_trust = 0.0
        d_freedom = 0.0
        d_conflict = 0.0
        d_brand_sentiment = 0.0
        d_purchase_intent = 0.0
        d_word_of_mouth = 0.0
        d_churn_risk = 0.0
        d_adoption_rate = 0.0

        for a in actions:
            at = a.action_type
            if at == ActionType.COMPLY:
                d_stability += 0.02
                d_trust += 0.005
                d_brand_sentiment += 0.01
                d_churn_risk -= 0.01
                d_adoption_rate += 0.02
            elif at == ActionType.VOTE:
                d_stability += 0.01
            elif at == ActionType.PROTEST:
                d_stability -= 0.05
                d_conflict += 0.03
                d_trust -= 0.02
                d_freedom += 0.03
                d_brand_sentiment -= 0.03
                d_purchase_intent -= 0.02
                d_word_of_mouth += 0.03
                d_churn_risk += 0.03
                d_adoption_rate -= 0.01
            elif at == ActionType.DEFECT:
                d_stability -= 0.08
                d_conflict += 0.05
                d_trust -= 0.04
                d_freedom += 0.04
                d_brand_sentiment -= 0.04
                d_purchase_intent -= 0.02
                d_word_of_mouth += 0.01
                d_churn_risk += 0.04
                d_adoption_rate -= 0.02
            elif at == ActionType.TRADE:
                d_prosperity += 0.01
                d_trust += 0.015
            elif at == ActionType.BUILD:
                d_prosperity += 0.02
            elif at == ActionType.FORM_GROUP:
                d_stability += 0.01
                d_trust += 0.01
            elif at == ActionType.PROPOSE_RULE:
                d_conflict += 0.02
            elif at == ActionType.SPEAK_PUBLIC:
                d_trust += 0.01
                d_word_of_mouth += 0.01
            elif at == ActionType.SPEAK_PRIVATE:
                d_trust -= 0.005
            elif at == ActionType.RECOMMEND:
                d_brand_sentiment += 0.01
                d_purchase_intent += 0.02
                d_word_of_mouth += 0.03
                d_churn_risk -= 0.01
                d_adoption_rate += 0.01
            elif at == ActionType.PURCHASE:
                d_brand_sentiment += 0.02
                d_purchase_intent += 0.01
                d_word_of_mouth += 0.01
                d_churn_risk -= 0.02
                d_adoption_rate += 0.03
                d_prosperity += 0.01
            elif at == ActionType.ABANDON:
                d_brand_sentiment -= 0.05
                d_purchase_intent -= 0.03
                d_word_of_mouth += 0.02
                d_churn_risk += 0.05
                d_adoption_rate -= 0.02
            elif at == ActionType.COMPARE:
                d_word_of_mouth += 0.02
            elif at == ActionType.RESEARCH:
                d_trust += 0.005
            elif at == ActionType.INVESTIGATE:
                d_trust += 0.01
                d_word_of_mouth += 0.01

            if a.world_state_changes.get("rule_passed"):
                d_freedom -= 0.03
                d_stability += 0.03
            if a.world_state_changes.get("rule_rejected"):
                d_freedom += 0.03
                d_stability -= 0.01
            if a.world_state_changes.get("institution_created"):
                d_freedom -= 0.02

        n_rules = len(world_state.community_rules)
        n_institutions = len(world_state.institutions)
        freedom_pressure = -0.005 * (n_rules + n_institutions)
        d_freedom += freedom_pressure

        if not any(a.action_type in (ActionType.PROTEST, ActionType.DEFECT) for a in actions):
            d_conflict -= 0.01
            d_trust += 0.005

        if not any(a.action_type in (ActionType.ABANDON, ActionType.PROTEST, ActionType.DEFECT) for a in actions):
            d_churn_risk -= 0.005
            d_brand_sentiment += 0.005

        for inst in world_state.institutions:
            member_count = len(inst.member_ids)
            if member_count >= 3:
                influence_bonus = 0.005 * member_count
                d_word_of_mouth += influence_bonus
                d_brand_sentiment += influence_bonus * 0.5

        def ema(old_val: float, delta: float) -> float:
            new = old_val + alpha * delta
            return max(0.0, min(1.0, new))

        return WorldMetrics(
            stability=ema(old.stability, d_stability),
            prosperity=ema(old.prosperity, d_prosperity),
            trust=ema(old.trust, d_trust),
            freedom=ema(old.freedom, d_freedom),
            conflict=ema(old.conflict, d_conflict),
            brand_sentiment=ema(old.brand_sentiment, d_brand_sentiment),
            purchase_intent=ema(old.purchase_intent, d_purchase_intent),
            word_of_mouth=ema(old.word_of_mouth, d_word_of_mouth),
            churn_risk=ema(old.churn_risk, d_churn_risk),
            adoption_rate=ema(old.adoption_rate, d_adoption_rate),
            information_spread=old.information_spread,
            echo_chamber_index=old.echo_chamber_index,
            rumor_distortion=old.rumor_distortion,
        )

    @staticmethod
    def _emotional_contagion(agents: list[AgentPersona]):
        """Emotions spread through the social graph. If most of your strong connections
        are angry/frustrated, you drift negative even if your own experience is fine.
        Gated by social_proof — high social_proof agents are more susceptible."""
        NEGATIVE_STATES = {"angry", "frustrated", "fearful", "hostile", "desperate"}
        POSITIVE_STATES = {"calm", "content", "curious", "satisfied", "hopeful"}
        SUSCEPTIBLE_STATES = POSITIVE_STATES | {"restless", "uneasy", "confused"}

        agent_map = {a.id: a for a in agents}
        changes: list[tuple[AgentPersona, str]] = []

        for agent in agents:
            if agent.emotional_state not in SUSCEPTIBLE_STATES:
                continue
            strong_neighbors = [
                e for e in agent.social_connections if e.strength > 0.5
            ]
            if not strong_neighbors:
                continue

            neighbor_states = []
            for edge in strong_neighbors:
                other = agent_map.get(edge.target_id)
                if other:
                    neighbor_states.append(other.emotional_state)

            if not neighbor_states:
                continue

            negative_ratio = sum(1 for s in neighbor_states if s in NEGATIVE_STATES) / len(neighbor_states)
            positive_ratio = sum(1 for s in neighbor_states if s in POSITIVE_STATES) / len(neighbor_states)

            susceptibility = agent.personality.social_proof * 0.6 + agent.personality.empathy * 0.3

            if negative_ratio > 0.5 and random.random() < negative_ratio * susceptibility:
                if agent.emotional_state in POSITIVE_STATES:
                    changes.append((agent, "uneasy"))
                elif agent.emotional_state in ("restless", "uneasy"):
                    changes.append((agent, "frustrated"))
            elif positive_ratio > 0.7 and agent.emotional_state in ("uneasy", "restless") and random.random() < 0.2:
                changes.append((agent, "calm"))

        for agent, new_state in changes:
            agent.emotional_state = new_state

    EMOTIONAL_DECAY_MAP = {
        "angry": "frustrated",
        "hostile": "angry",
        "desperate": "fearful",
        "fearful": "anxious",
        "frustrated": "restless",
        "restless": "uneasy",
        "uneasy": "calm",
        "anxious": "uneasy",
    }

    @classmethod
    def _emotional_decay(cls, agents: list[AgentPersona]):
        """Without reinforcement, extreme emotions gradually fade.
        Base ~25% chance per round, boosted for conformist/loyal agents who
        psychologically accept changes faster. This counterbalances contagion
        to prevent uniform negativity cascades."""
        for agent in agents:
            if agent.emotional_state in cls.EMOTIONAL_DECAY_MAP:
                p = agent.personality
                decay_prob = 0.25
                if p.conformity >= 0.6:
                    decay_prob += 0.12
                if p.brand_loyalty >= 0.6:
                    decay_prob += 0.10
                if p.confrontational <= 0.3:
                    decay_prob += 0.08
                if random.random() < min(0.65, decay_prob):
                    agent.emotional_state = cls.EMOTIONAL_DECAY_MAP[agent.emotional_state]
