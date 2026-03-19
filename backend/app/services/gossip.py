from __future__ import annotations
import logging
import random
import uuid
from pydantic import BaseModel, Field

from app.models.agent import AgentPersona, SocialEdge
from app.models.action import ActionType, ActionEntry, ReactiveResponse

logger = logging.getLogger(__name__)

GOSSIP_WORTHY_ACTIONS = {
    ActionType.SPEAK_PUBLIC,
    ActionType.PROTEST,
    ActionType.DEFECT,
    ActionType.FORM_GROUP,
    ActionType.PROPOSE_RULE,
    ActionType.PURCHASE,
    ActionType.ABANDON,
    ActionType.RECOMMEND,
    ActionType.COMPARE,
    ActionType.TRADE,
    ActionType.BUILD,
}


class InfoItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    content: str
    original_source_id: int
    original_source_name: str
    source_chain: list[int] = Field(default_factory=list)
    hops: int = 0
    sentiment_bias: float = 0.0
    round_created: int = 0
    round_received: int = 0
    action_type: str = ""
    expired: bool = False


class GossipEngine:
    """Manages hop-by-hop information propagation through the social graph."""

    MAX_HOPS = 4
    MAX_INFO_AGE = 9
    MAX_ITEMS_PER_AGENT = 12

    def __init__(self):
        self._info_pool: dict[str, dict[int, list[InfoItem]]] = {}

    def init_simulation(self, sim_id: str):
        self._info_pool[sim_id] = {}

    def cleanup(self, sim_id: str):
        self._info_pool.pop(sim_id, None)

    def _get_pool(self, sim_id: str) -> dict[int, list[InfoItem]]:
        if sim_id not in self._info_pool:
            self._info_pool[sim_id] = {}
        return self._info_pool[sim_id]

    def propagate(
        self,
        sim_id: str,
        resolved_entries: list[ActionEntry],
        reactions: list[ReactiveResponse],
        agents: list[AgentPersona],
        round_num: int,
        day: int,
        time_of_day: str,
        is_market: bool,
    ) -> None:
        pool = self._get_pool(sim_id)
        agent_map = {a.id: a for a in agents}
        conn_map = self._build_conn_map(agents)

        self._expire_old(pool, round_num)

        new_items = self._create_info_items(
            resolved_entries, reactions, agents, round_num, is_market,
        )

        self._deliver_firsthand(
            new_items, resolved_entries, agents, pool, conn_map, round_num,
        )

        self._relay_existing(pool, agents, agent_map, conn_map, round_num)

        self._write_memories(
            pool, resolved_entries, agents, agent_map, round_num, day, time_of_day, is_market,
        )

        self._echo_chamber_reinforcement(pool, agents, conn_map)

    @staticmethod
    def _build_conn_map(agents: list[AgentPersona]) -> dict[int, list[SocialEdge]]:
        return {a.id: list(a.social_connections) for a in agents}

    def _expire_old(self, pool: dict[int, list[InfoItem]], round_num: int):
        for aid in pool:
            pool[aid] = [
                item for item in pool[aid]
                if (round_num - item.round_created) < self.MAX_INFO_AGE and not item.expired
            ]

    @staticmethod
    def _summarize_action(entry: ActionEntry, is_market: bool) -> str | None:
        at = entry.action_type
        if at == ActionType.SPEAK_PUBLIC and entry.speech:
            return f'{entry.agent_name} said: "{entry.speech[:80]}"'
        if at == ActionType.PURCHASE:
            return f"{entry.agent_name} bought {entry.action_args.get('product', 'the product')}"
        if at == ActionType.ABANDON:
            reason = entry.action_args.get("reason", "")
            return f"{entry.agent_name} left {entry.action_args.get('product', 'the product')}" + (f" — {reason[:50]}" if reason else "")
        if at == ActionType.RECOMMEND:
            return f"{entry.agent_name} recommended {entry.action_args.get('product', 'the product')}"
        if at == ActionType.COMPARE:
            return f"{entry.agent_name} compared {entry.action_args.get('product_a', '')} vs {entry.action_args.get('product_b', '')}"
        if at == ActionType.PROTEST:
            return f"{entry.agent_name} protested: {entry.action_args.get('target', 'something')[:60]}"
        if at == ActionType.DEFECT:
            return f"{entry.agent_name} broke the rules: {entry.action_args.get('how', '')[:50]}"
        if at == ActionType.FORM_GROUP:
            return f"{entry.agent_name} formed a group: {entry.action_args.get('name', 'a new group')}"
        if at == ActionType.PROPOSE_RULE:
            return f"{entry.agent_name} proposed a rule: {entry.action_args.get('content', '')[:50]}"
        if at == ActionType.TRADE:
            return f"{entry.agent_name} traded with someone"
        if at == ActionType.BUILD:
            return f"{entry.agent_name} built {entry.action_args.get('what', 'something')}"
        return None

    def _create_info_items(
        self,
        entries: list[ActionEntry],
        reactions: list[ReactiveResponse],
        agents: list[AgentPersona],
        round_num: int,
        is_market: bool,
    ) -> list[InfoItem]:
        items: list[InfoItem] = []
        for entry in entries:
            if entry.action_type not in GOSSIP_WORTHY_ACTIONS:
                continue
            content = self._summarize_action(entry, is_market)
            if not content:
                continue
            items.append(InfoItem(
                content=content,
                original_source_id=entry.agent_id,
                original_source_name=entry.agent_name,
                source_chain=[entry.agent_id],
                hops=0,
                sentiment_bias=0.0,
                round_created=round_num,
                round_received=round_num,
                action_type=entry.action_type.value,
            ))

        for reaction in reactions:
            if reaction.reaction_type == "silent" or not reaction.content:
                continue
            items.append(InfoItem(
                content=f'{reaction.agent_name} reacted: "{reaction.content[:80]}"',
                original_source_id=reaction.agent_id,
                original_source_name=reaction.agent_name,
                source_chain=[reaction.agent_id],
                hops=0,
                sentiment_bias=0.0,
                round_created=round_num,
                round_received=round_num,
                action_type="REACTION",
            ))
        return items

    def _deliver_firsthand(
        self,
        new_items: list[InfoItem],
        entries: list[ActionEntry],
        agents: list[AgentPersona],
        pool: dict[int, list[InfoItem]],
        conn_map: dict[int, list[SocialEdge]],
        round_num: int,
    ):
        source_targets: dict[int, set[int]] = {}
        for entry in entries:
            if entry.agent_id not in source_targets:
                source_targets[entry.agent_id] = set()
            source_targets[entry.agent_id].update(entry.targets or [])

        for item in new_items:
            source_id = item.original_source_id
            source_conns = conn_map.get(source_id, [])
            strong_neighbors = {e.target_id for e in source_conns if e.strength > 0.6}
            interaction_targets = source_targets.get(source_id, set())

            for agent in agents:
                if agent.id == source_id:
                    continue

                is_direct_witness = (
                    agent.id in strong_neighbors
                    or agent.id in interaction_targets
                )

                if not is_direct_witness:
                    if agent.social_connections:
                        any_mutual = any(
                            e.target_id == source_id and e.strength > 0.5
                            for e in agent.social_connections
                        )
                        if not any_mutual:
                            continue
                    else:
                        if random.random() > 0.08:
                            continue

                delivered = item.model_copy(update={
                    "round_received": round_num,
                    "hops": 0,
                })
                if agent.id not in pool:
                    pool[agent.id] = []
                if not any(existing.id == delivered.id for existing in pool[agent.id]):
                    pool[agent.id].append(delivered)

            if source_id not in pool:
                pool[source_id] = []
            own_copy = item.model_copy()
            if not any(existing.id == own_copy.id for existing in pool[source_id]):
                pool[source_id].append(own_copy)

    def _relay_existing(
        self,
        pool: dict[int, list[InfoItem]],
        agents: list[AgentPersona],
        agent_map: dict[int, AgentPersona],
        conn_map: dict[int, list[SocialEdge]],
        round_num: int,
    ):
        relay_queue: list[tuple[int, InfoItem]] = []

        for agent in agents:
            known = pool.get(agent.id, [])
            for item in known:
                if item.hops >= self.MAX_HOPS:
                    continue
                if item.round_received == round_num:
                    continue

                relay_prob = 0.3 + agent.personality.social_proof * 0.3
                if agent.personality.confrontational > 0.6 and "protest" in item.content.lower():
                    relay_prob += 0.2
                if agent.emotional_state in ("angry", "frustrated", "restless"):
                    relay_prob += 0.15

                if random.random() > relay_prob:
                    continue

                bias_delta = self._compute_distortion(agent, item)

                for edge in conn_map.get(agent.id, []):
                    if edge.target_id in item.source_chain:
                        continue
                    spread_prob = edge.strength * 0.8
                    if random.random() > spread_prob:
                        continue

                    relayed = item.model_copy(update={
                        "source_chain": item.source_chain + [agent.id],
                        "hops": item.hops + 1,
                        "sentiment_bias": max(-1.0, min(1.0, item.sentiment_bias + bias_delta)),
                        "round_received": round_num,
                    })
                    relay_queue.append((edge.target_id, relayed))

        for target_id, relayed_item in relay_queue:
            if target_id not in pool:
                pool[target_id] = []
            if not any(existing.id == relayed_item.id for existing in pool[target_id]):
                pool[target_id].append(relayed_item)

    @staticmethod
    def _compute_distortion(relayer: AgentPersona, item: InfoItem) -> float:
        bias = 0.0
        if relayer.personality.honesty < 0.3:
            bias += random.uniform(-0.15, 0.15)
        if relayer.personality.empathy > 0.7:
            if item.sentiment_bias < 0:
                bias += 0.1
        if relayer.personality.confrontational > 0.7:
            if "protest" in item.content.lower() or "broke" in item.content.lower():
                bias -= 0.1

        if relayer.faction:
            same_faction = False
            for part in item.source_chain:
                pass
            bias += random.uniform(-0.05, 0.05)

        return bias

    def _write_memories(
        self,
        pool: dict[int, list[InfoItem]],
        resolved_entries: list[ActionEntry],
        agents: list[AgentPersona],
        agent_map: dict[int, AgentPersona],
        round_num: int,
        day: int,
        time_of_day: str,
        is_market: bool,
    ):
        active_ids = {e.agent_id for e in resolved_entries}

        for agent in agents:
            if agent.id in active_ids:
                my_actions = [e for e in resolved_entries if e.agent_id == agent.id]
                summary = f"Day {day} {time_of_day}: "
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
                summary += "; ".join(parts) if parts else "A quiet period."
                agent.working_memory.append(summary)
            else:
                my_info = pool.get(agent.id, [])
                new_info = [
                    item for item in my_info
                    if item.round_received == round_num and item.original_source_id != agent.id
                ]

                if new_info:
                    self._upgrade_knowledge(agent, new_info)
                    heard_parts = []
                    for item in new_info[:5]:
                        framed = self._frame_info(item, agent)
                        heard_parts.append(framed)

                    summary = f"Day {day} {time_of_day}: Heard: " + "; ".join(heard_parts)
                else:
                    summary = f"Day {day} {time_of_day}: A quiet period."

                agent.working_memory.append(summary)

            if len(agent.working_memory) > 9:
                agent.working_memory = agent.working_memory[-9:]

    @staticmethod
    def _upgrade_knowledge(agent: AgentPersona, info_items: list[InfoItem]):
        """Upgrade agent's knowledge_level when they hear about the change through gossip."""
        if getattr(agent, "knowledge_level", "full") == "full":
            return
        change_keywords = ("price", "hike", "increase", "ads", "ad", "cancel", "subscription", "cost")
        for item in info_items:
            content_lower = item.content.lower()
            if any(kw in content_lower for kw in change_keywords):
                current = getattr(agent, "knowledge_level", "full")
                if current == "unaware":
                    agent.knowledge_level = "partial"
                elif current == "partial" and item.hops <= 1:
                    agent.knowledge_level = "full"
                break

    @staticmethod
    def _frame_info(item: InfoItem, receiver: AgentPersona) -> str:
        content = item.content

        if item.hops == 0:
            source_tag = "(firsthand)"
        elif item.hops == 1:
            source_tag = "(heard from someone)"
        else:
            source_tag = f"(rumor, {item.hops} hops)"

        if item.sentiment_bias > 0.3:
            sentiment_tag = " — people seem to approve"
        elif item.sentiment_bias < -0.3:
            sentiment_tag = " — people are upset about this"
        else:
            sentiment_tag = ""

        return f"{content} {source_tag}{sentiment_tag}"

    @staticmethod
    def _echo_chamber_reinforcement(
        pool: dict[int, list[InfoItem]],
        agents: list[AgentPersona],
        conn_map: dict[int, list[SocialEdge]],
    ):
        for agent in agents:
            if not agent.faction:
                continue
            for edge in agent.social_connections:
                other = next((a for a in agents if a.id == edge.target_id), None)
                if not other:
                    continue
                if other.faction == agent.faction:
                    edge.strength = min(1.0, edge.strength + 0.02)
                    for other_edge in other.social_connections:
                        if other_edge.target_id == agent.id:
                            other_edge.strength = min(1.0, other_edge.strength + 0.02)
                            break

    def inject_event_via_gossip(
        self,
        sim_id: str,
        event_desc: str,
        agents: list[AgentPersona],
        round_num: int,
        day: int,
        initial_recipients: list[int] | None = None,
    ):
        pool = self._get_pool(sim_id)

        item = InfoItem(
            content=f"EVENT — {event_desc[:100]}",
            original_source_id=-1,
            original_source_name="world",
            source_chain=[-1],
            hops=0,
            sentiment_bias=0.0,
            round_created=round_num,
            round_received=round_num,
            action_type="TENSION_EVENT",
        )

        if initial_recipients:
            recipients = initial_recipients
        else:
            count = max(3, len(agents) // 3)
            recipients = [a.id for a in random.sample(agents, min(count, len(agents)))]

        for aid in recipients:
            if aid not in pool:
                pool[aid] = []
            delivered = item.model_copy(update={"round_received": round_num})
            pool[aid].append(delivered)

            agent = next((a for a in agents if a.id == aid), None)
            if agent:
                agent.working_memory.append(f"Day {day}: EVENT — {event_desc[:100]}")
                if len(agent.working_memory) > 9:
                    agent.working_memory = agent.working_memory[-9:]

    def compute_gossip_metrics(
        self, sim_id: str, agents: list[AgentPersona],
        round_num: int = 0,
    ) -> dict[str, float]:
        pool = self._get_pool(sim_id)
        total_agents = len(agents)

        if total_agents == 0:
            return {"information_spread": 0.0, "echo_chamber_index": 0.0, "rumor_distortion": 0.0}

        recent_window = 3
        all_recent_ids: set[str] = set()
        for items in pool.values():
            for item in items:
                if round_num - item.round_created < recent_window:
                    all_recent_ids.add(item.id)

        total_unique = len(all_recent_ids)
        if total_unique == 0:
            information_spread = 0.0
        else:
            agent_ids = {a.id for a in agents}
            coverage_sum = 0.0
            for aid in agent_ids:
                agent_items = pool.get(aid, [])
                agent_recent = {it.id for it in agent_items if round_num - it.round_created < recent_window}
                coverage_sum += len(agent_recent) / total_unique
            information_spread = coverage_sum / total_agents

        all_biases = []
        for items in pool.values():
            for item in items:
                all_biases.append(abs(item.sentiment_bias))
        rumor_distortion = sum(all_biases) / len(all_biases) if all_biases else 0.0

        intra_faction = 0
        inter_faction = 0
        for agent in agents:
            if not agent.faction:
                continue
            for edge in agent.social_connections:
                other = next((a for a in agents if a.id == edge.target_id), None)
                if not other:
                    continue
                if other.faction == agent.faction:
                    intra_faction += edge.strength
                elif other.faction:
                    inter_faction += edge.strength

        total_faction_flow = intra_faction + inter_faction
        echo_chamber_index = intra_faction / total_faction_flow if total_faction_flow > 0 else 0.0

        return {
            "information_spread": min(1.0, information_spread),
            "echo_chamber_index": min(1.0, echo_chamber_index),
            "rumor_distortion": min(1.0, rumor_distortion),
        }

    def social_neighbors(
        self, agent: AgentPersona, all_agents: list[AgentPersona], count: int = 5,
    ) -> list[AgentPersona]:
        agent_map = {a.id: a for a in all_agents if a.id != agent.id}
        if not agent_map:
            return []

        if not agent.social_connections:
            others = list(agent_map.values())
            return random.sample(others, min(count, len(others)))

        weighted: list[tuple[int, float]] = []
        connected_ids = set()
        for edge in agent.social_connections:
            if edge.target_id in agent_map:
                weighted.append((edge.target_id, edge.strength))
                connected_ids.add(edge.target_id)

        strangers = [aid for aid in agent_map if aid not in connected_ids]
        for sid in strangers:
            weighted.append((sid, 0.08))

        if not weighted:
            return []

        ids = [w[0] for w in weighted]
        weights = [w[1] for w in weighted]

        selected_ids: list[int] = []
        for _ in range(min(count, len(ids))):
            if not ids:
                break
            pick = random.choices(range(len(ids)), weights=weights, k=1)[0]
            selected_ids.append(ids[pick])
            ids.pop(pick)
            weights.pop(pick)

        return [agent_map[aid] for aid in selected_ids if aid in agent_map]
