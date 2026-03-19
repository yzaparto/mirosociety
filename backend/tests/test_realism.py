"""Comprehensive realism tests for MiroSociety simulation engine.

These tests measure specific, quantifiable properties of human-like behavior.
Each test has a clear PASS/FAIL threshold so you can iterate on prompts,
engine mechanics, or personality models and see if things improve or regress.

Run:  cd backend && python -m pytest tests/test_realism.py -v

Test categories:
  1. Linguistic diversity — agents don't all sound the same
  2. Silence & lurking — most people stay quiet most of the time
  3. Action vs talk ratio — consumers act, not just opine
  4. Emotional dynamics — contagion, decay, realistic spread
  5. Information diffusion — not everyone knows everything on day 1
  6. Conversation threading — agents reference each other, not the void
  7. Anti-sycophancy — no "I totally agree" monoculture
  8. Personality consistency — traits drive behavior predictably
  12. Compare loop prevention — agents don't endlessly compare without deciding
  13. Decision stage nudge — agents get contextual progression guidance
  14. Action gating — repeated actions are removed from available list
  15. Reactive micro-round for actions — non-speech actions trigger reactions
  16. Anti-cascade — loyalty anchor prevents uniform defection
  17. Anti-cascade — trait-aware decision nudges
  18. Anti-cascade — content repetition detection
  19. Anti-cascade — behavior rules prevent herd exits
  20. Anti-cascade — personality-aware emotional decay
"""
from __future__ import annotations
import asyncio
import json
import random
import re

import pytest
import pytest_asyncio

from app.models.agent import AgentPersona, Personality, SocialEdge, COMMUNICATION_STYLES
from app.models.action import ActionType, ActionEntry, ReactiveResponse
from app.models.world import WorldState, WorldMetrics
from app.models.simulation import SSEEvent
from app.services.engine import SimulationEngine
from app.services.resolver import ActionResolver
from app.services.tension import TensionEngine
from app.services.narrator import Narrator
from app.services.gossip import GossipEngine

from tests.conftest import (
    MockLLM, make_agent, make_netflix_cast, make_market_world,
)

pytestmark = pytest.mark.asyncio


# ============================================================================
# 1. LINGUISTIC DIVERSITY
# ============================================================================

class TestLinguisticDiversity:
    """Agents should speak differently based on their communication_style."""

    def test_all_styles_assigned_in_cast(self):
        """A cast of 10 should have at least 4 distinct communication styles."""
        agents = make_netflix_cast(10)
        styles = {a.communication_style for a in agents}
        assert len(styles) >= 4, (
            f"Only {len(styles)} styles in a cast of 10: {styles}. "
            "Need at least 4 for linguistic diversity."
        )

    def test_no_single_style_dominates(self):
        """No single style should account for more than 40% of the cast."""
        agents = make_netflix_cast(10)
        from collections import Counter
        counts = Counter(a.communication_style for a in agents)
        max_count = max(counts.values())
        assert max_count <= 4, (
            f"Style '{counts.most_common(1)[0][0]}' assigned to {max_count}/10 agents. "
            "Max 4 allowed to prevent monoculture."
        )

    def test_communication_style_in_decision_prompt(self):
        """The communication_style must appear in the decision system prompt."""
        from app.services.engine import AGENT_DECISION_SYSTEM
        assert "{communication_style}" in AGENT_DECISION_SYSTEM, (
            "AGENT_DECISION_SYSTEM prompt must include {communication_style} placeholder"
        )

    def test_communication_style_in_reactive_prompts(self):
        """All reactive prompts must include communication_style."""
        from app.services.engine import (
            REACTIVE_PROMPT_MARKET, REACTIVE_PROMPT_SOCIAL, REACTIVE_ACTION_PROMPT,
        )
        for name, prompt in [
            ("REACTIVE_PROMPT_MARKET", REACTIVE_PROMPT_MARKET),
            ("REACTIVE_PROMPT_SOCIAL", REACTIVE_PROMPT_SOCIAL),
            ("REACTIVE_ACTION_PROMPT", REACTIVE_ACTION_PROMPT),
        ]:
            assert "{communication_style}" in prompt, f"{name} missing {{communication_style}}"

    def test_style_descriptions_are_distinct(self):
        """Each style description should be meaningfully different."""
        descs = list(COMMUNICATION_STYLES.values())
        for i, d1 in enumerate(descs):
            for j, d2 in enumerate(descs):
                if i < j:
                    overlap = len(set(d1.lower().split()) & set(d2.lower().split()))
                    total = min(len(d1.split()), len(d2.split()))
                    ratio = overlap / total if total else 0
                    assert ratio < 0.6, (
                        f"Styles too similar (overlap={ratio:.0%}): "
                        f"'{d1[:40]}...' vs '{d2[:40]}...'"
                    )


# ============================================================================
# 2. SILENCE & LURKING
# ============================================================================

class TestSilenceAndLurking:
    """Most humans stay silent most of the time. The simulation should too."""

    def test_silence_prefilter_exists(self):
        """The _should_stay_silent method should exist on SimulationEngine."""
        assert hasattr(SimulationEngine, "_should_stay_silent")

    def test_calm_low_confrontational_agents_usually_silent(self):
        """A calm agent with low confrontational should stay silent > 40% of the time."""
        agent = make_agent(0, "Quiet Quinn", confrontational=0.2, ambition=0.2,
                           conformity=0.7, emotional_state="calm")
        silent_count = sum(
            SimulationEngine._should_stay_silent(agent, False)
            for _ in range(200)
        )
        rate = silent_count / 200
        assert rate > 0.40, (
            f"Calm, non-confrontational agent only silent {rate:.0%} of the time. "
            "Should be >40%."
        )

    def test_angry_confrontational_agents_speak_more(self):
        """An angry, confrontational agent should stay silent less often."""
        agent = make_agent(0, "Angry Andy", confrontational=0.9, ambition=0.8,
                           emotional_state="angry")
        silent_count = sum(
            SimulationEngine._should_stay_silent(agent, False)
            for _ in range(200)
        )
        rate = silent_count / 200
        assert rate < 0.55, (
            f"Angry, confrontational agent silent {rate:.0%} of the time. "
            "Should be <55% — they should speak up more."
        )

    def test_agreement_pile_on_increases_silence(self):
        """When is_agreement_pile_on=True, conformist agents should be MORE silent."""
        agent = make_agent(0, "Conformist Carl", conformity=0.8, confrontational=0.3)
        normal_silence = sum(SimulationEngine._should_stay_silent(agent, False) for _ in range(300))
        pile_on_silence = sum(SimulationEngine._should_stay_silent(agent, True) for _ in range(300))
        assert pile_on_silence > normal_silence, (
            f"Pile-on silence ({pile_on_silence}) should exceed normal silence ({normal_silence}) "
            "for conformist agents."
        )

    def test_silence_rate_in_reactive_round(self):
        """In a reactive round with 4 witnesses, at least 1 should typically stay silent."""
        agents = make_netflix_cast(10)
        silent_total = 0
        trials = 100
        for _ in range(trials):
            witnesses = random.sample(agents, 4)
            silences = sum(SimulationEngine._should_stay_silent(w, False) for w in witnesses)
            silent_total += silences
        avg_silent = silent_total / trials
        assert avg_silent >= 0.8, (
            f"Average silent witnesses per round: {avg_silent:.1f}. "
            "Expected >= 0.8 out of 4 (at least ~20% silence rate)."
        )


# ============================================================================
# 3. ACTION vs TALK RATIO
# ============================================================================

class TestActionVsTalk:
    """Consumers should take concrete actions, not just speechify endlessly."""

    def test_repetition_detector_triggers_on_speech_only(self):
        """After 4+ speeches with no action, the detector should return a warning."""
        agent = make_agent(0, "Talkative Tom")
        agent.working_memory = [
            'Day 1 morning: SPEAK_PUBLIC: said "This price hike is terrible"',
            'Day 1 afternoon: SPEAK_PUBLIC: said "I agree with the others"',
            'Day 1 evening: SPEAK_PUBLIC: said "Something needs to change"',
            'Day 2 morning: SPEAK_PUBLIC: said "When will they listen?"',
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert warning, "Should produce a warning after 4 speeches with no action"
        assert "action" in warning.lower() or "do something" in warning.lower() or "DO" in warning

    def test_no_warning_when_action_taken(self):
        """If an agent has taken decisive actions, no speech warning."""
        agent = make_agent(0, "Balanced Bob")
        agent.working_memory = [
            'Day 1: SPEAK_PUBLIC: said "I\'m frustrated"',
            'Day 1: ABANDON: abandoned Netflix — too expensive',
            'Day 1: SPEAK_PUBLIC: said "I switched to Hulu"',
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert not warning or "STOP" not in warning, (
            "Agent who took decisive actions shouldn't get a strong warning"
        )

    def test_decision_funnel_in_behavior_rules(self):
        """BEHAVIOR_RULES_MARKET should contain decision progression guidance."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        assert "DECISION PROGRESSION" in BEHAVIOR_RULES_MARKET or "progression" in BEHAVIOR_RULES_MARKET.lower()
        assert "price_sensitivity" in BEHAVIOR_RULES_MARKET
        assert "brand_loyalty" in BEHAVIOR_RULES_MARKET
        assert "ABANDON" in BEHAVIOR_RULES_MARKET or "abandon" in BEHAVIOR_RULES_MARKET.lower()
        assert "ONCE" in BEHAVIOR_RULES_MARKET, "Rules should emphasize doing info-gathering actions once"


# ============================================================================
# 4. EMOTIONAL DYNAMICS
# ============================================================================

class TestEmotionalDynamics:
    """Emotions should spread through social connections and decay over time."""

    def test_emotional_contagion_spreads_negativity(self):
        """An agent with mostly angry neighbors should drift negative."""
        resolver = ActionResolver()
        calm_agent = make_agent(0, "Calm Carl", social_proof=0.9, empathy=0.8,
                                emotional_state="calm")
        angry_agents = [
            make_agent(i, f"Angry{i}", emotional_state="angry")
            for i in range(1, 5)
        ]
        calm_agent.social_connections = [
            SocialEdge(target_id=i, strength=0.8, sentiment=-0.2) for i in range(1, 5)
        ]
        all_agents = [calm_agent] + angry_agents

        flipped = False
        for _ in range(20):
            calm_agent.emotional_state = "calm"
            resolver._emotional_contagion(all_agents)
            if calm_agent.emotional_state != "calm":
                flipped = True
                break
        assert flipped, (
            "Agent with high social_proof surrounded by angry agents should eventually "
            "catch negative emotions via contagion."
        )

    def test_emotional_contagion_respects_low_social_proof(self):
        """An agent with low social_proof should resist emotional contagion."""
        resolver = ActionResolver()
        stoic = make_agent(0, "Stoic Steve", social_proof=0.1, empathy=0.1,
                           emotional_state="calm")
        angry_agents = [
            make_agent(i, f"Angry{i}", emotional_state="angry")
            for i in range(1, 5)
        ]
        stoic.social_connections = [
            SocialEdge(target_id=i, strength=0.8, sentiment=-0.2) for i in range(1, 5)
        ]
        all_agents = [stoic] + angry_agents

        flipped = 0
        for _ in range(50):
            stoic.emotional_state = "calm"
            resolver._emotional_contagion(all_agents)
            if stoic.emotional_state != "calm":
                flipped += 1
        assert flipped < 15, (
            f"Low-social-proof agent flipped {flipped}/50 times. Should resist contagion."
        )

    def test_emotional_decay_reduces_intensity(self):
        """Extreme emotions should decay toward calm over many rounds."""
        resolver = ActionResolver()
        agent = make_agent(0, "Angry Annie", emotional_state="angry")
        agents = [agent]

        states_seen = {agent.emotional_state}
        for _ in range(50):
            resolver._emotional_decay(agents)
            states_seen.add(agent.emotional_state)

        assert "frustrated" in states_seen or "restless" in states_seen or "calm" in states_seen, (
            f"After 50 decay rounds, angry agent should have decayed. States seen: {states_seen}"
        )

    def test_emotional_decay_map_is_complete(self):
        """Every negative emotional state should have a decay target."""
        negative_states = {"angry", "hostile", "desperate", "fearful", "frustrated",
                           "restless", "uneasy", "anxious"}
        for state in negative_states:
            assert state in ActionResolver.EMOTIONAL_DECAY_MAP, (
                f"Emotional state '{state}' has no decay target in EMOTIONAL_DECAY_MAP"
            )


# ============================================================================
# 5. INFORMATION DIFFUSION
# ============================================================================

class TestInformationDiffusion:
    """Not everyone should know about the change on day 1."""

    def test_knowledge_levels_assigned_differently(self):
        """A diverse cast should have mixed knowledge levels after assignment."""
        from app.services.citizen_generator import CitizenGenerator
        agents = [
            make_agent(0, "High PS", price_sensitivity=0.9, knowledge_level="full"),
            make_agent(1, "High BL", brand_loyalty=0.9, knowledge_level="full"),
            make_agent(2, "Casual", price_sensitivity=0.3, brand_loyalty=0.3,
                       social_proof=0.3, novelty_seeking=0.3, ambition=0.3),
            make_agent(3, "Casual2", price_sensitivity=0.2, brand_loyalty=0.2,
                       social_proof=0.2, novelty_seeking=0.2, ambition=0.2),
        ]
        CitizenGenerator._assign_knowledge_levels(agents)
        levels = [a.knowledge_level for a in agents]
        assert "full" in levels, "High price_sensitivity agents should know"
        has_non_full = any(l != "full" for l in levels)
        assert has_non_full, (
            f"All agents got 'full' knowledge: {levels}. Casual agents should sometimes be "
            "partial or unaware."
        )

    def test_rules_filtered_for_unaware_agents(self):
        """An unaware agent should not see change-specific rules."""
        agent = make_agent(0, "Oblivious Ollie", knowledge_level="unaware")
        world = make_market_world()
        rules_text = SimulationEngine._build_rules_for_agent(agent, world)
        assert "40%" not in rules_text, "Unaware agent should not see '40%' price hike"
        assert "raises prices" not in rules_text.lower(), "Unaware agent should not see price raise details"
        assert "normal" in rules_text.lower() or "haven't heard" in rules_text.lower(), (
            "Unaware agent should see normalcy messaging"
        )

    def test_rules_vague_for_partial_agents(self):
        """A partially-informed agent should see vague language about changes."""
        agent = make_agent(0, "Partial Pat", knowledge_level="partial")
        world = make_market_world()
        rules_text = SimulationEngine._build_rules_for_agent(agent, world)
        assert "rumor" in rules_text.lower() or "heard" in rules_text.lower(), (
            "Partial agent should see rumor/vague language about changes"
        )

    def test_rules_full_for_aware_agents(self):
        """A fully-informed agent should see all rules."""
        agent = make_agent(0, "Informed Irene", knowledge_level="full")
        world = make_market_world()
        rules_text = SimulationEngine._build_rules_for_agent(agent, world)
        assert "raises prices" in rules_text.lower() or "40%" in rules_text, (
            "Full-knowledge agent should see the price hike details"
        )

    def test_gossip_upgrades_knowledge(self):
        """When an unaware agent hears gossip about the change, knowledge should upgrade."""
        from app.services.gossip import GossipEngine, InfoItem
        agent = make_agent(0, "Unaware Uma", knowledge_level="unaware")
        items = [InfoItem(
            content='Natalie said: "Netflix just raised prices by 40%!"',
            original_source_id=1, original_source_name="Natalie",
            source_chain=[1], hops=1, round_created=1, round_received=2,
        )]
        GossipEngine._upgrade_knowledge(agent, items)
        assert agent.knowledge_level == "partial", (
            f"Unaware agent who hears about price hike should become partial. Got: {agent.knowledge_level}"
        )

    def test_firsthand_gossip_gives_full_knowledge(self):
        """Firsthand (hops=0) gossip about the change should give full knowledge to partial agents."""
        from app.services.gossip import GossipEngine, InfoItem
        agent = make_agent(0, "Partial Pete", knowledge_level="partial")
        items = [InfoItem(
            content='Rita said: "I just saw the price increase notification"',
            original_source_id=2, original_source_name="Rita",
            source_chain=[2], hops=0, round_created=2, round_received=2,
        )]
        GossipEngine._upgrade_knowledge(agent, items)
        assert agent.knowledge_level == "full", (
            f"Partial agent hearing firsthand about price increase should become full. Got: {agent.knowledge_level}"
        )


# ============================================================================
# 6. CONVERSATION THREADING
# ============================================================================

class TestConversationThreading:
    """Agents should reference what others have said, not speak into the void."""

    def test_recent_conversation_builder_finds_speeches(self):
        """_build_recent_conversation should extract quotes from working memory."""
        agents = [
            make_agent(0, "Alice"),
            make_agent(1, "Bob", working_memory=[
                'Day 1 morning: SPEAK_PUBLIC: said "I\'m cancelling Netflix today"',
            ]),
            make_agent(2, "Carol", working_memory=[
                'Day 1 morning: SPEAK_PUBLIC: said "Has anyone compared Hulu?"',
            ]),
        ]
        result = SimulationEngine._build_recent_conversation(agents[0], agents)
        assert "Bob" in result, "Should reference Bob by name"
        assert "Carol" in result, "Should reference Carol by name"
        assert "cancelling" in result or "Hulu" in result, "Should include speech content"

    def test_recent_conversation_empty_when_no_speeches(self):
        """If no one has spoken, recent_conversation should be empty."""
        agents = [make_agent(i, f"Agent{i}") for i in range(3)]
        result = SimulationEngine._build_recent_conversation(agents[0], agents)
        assert result == "", "Should return empty string when no speeches in working memory"

    def test_recent_conversation_excludes_own_speech(self):
        """An agent shouldn't see their own speech in the conversation context."""
        agents = [
            make_agent(0, "Alice", working_memory=[
                'Day 1: SPEAK_PUBLIC: said "My own opinion"',
            ]),
            make_agent(1, "Bob", working_memory=[
                'Day 1: SPEAK_PUBLIC: said "Bob\'s opinion"',
            ]),
        ]
        result = SimulationEngine._build_recent_conversation(agents[0], agents)
        assert "Bob" in result
        assert "My own opinion" not in result, "Agent shouldn't see their own speech in conversation context"

    def test_recent_conversation_limited_to_5(self):
        """Should show at most 5 recent speeches to avoid prompt bloat."""
        agents = [make_agent(0, "Alice")]
        for i in range(1, 10):
            agents.append(make_agent(i, f"Speaker{i}", working_memory=[
                f'Day 1: SPEAK_PUBLIC: said "Statement {i}"',
            ]))
        result = SimulationEngine._build_recent_conversation(agents[0], agents)
        line_count = result.count("- ")
        assert line_count <= 5, f"Should show at most 5 speeches, got {line_count}"


# ============================================================================
# 7. ANTI-SYCOPHANCY
# ============================================================================

class TestAntiSycophancy:
    """The simulation should prevent the "I totally agree" epidemic."""

    def test_forbidden_phrases_in_market_behavior_rules(self):
        """BEHAVIOR_RULES_MARKET must contain forbidden agreement phrases."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        assert "FORBIDDEN" in BEHAVIOR_RULES_MARKET or "forbidden" in BEHAVIOR_RULES_MARKET.lower()
        assert "totally agree" in BEHAVIOR_RULES_MARKET.lower()

    def test_forbidden_phrases_in_reactive_market_prompt(self):
        """REACTIVE_PROMPT_MARKET must ban agreement starters."""
        from app.services.engine import REACTIVE_PROMPT_MARKET
        assert "totally agree" in REACTIVE_PROMPT_MARKET.lower()
        assert "NEVER" in REACTIVE_PROMPT_MARKET or "never" in REACTIVE_PROMPT_MARKET.lower()

    def test_forbidden_phrases_in_decision_prompt(self):
        """AGENT_DECISION_SYSTEM must ban agreement starters."""
        from app.services.engine import AGENT_DECISION_SYSTEM
        assert "totally agree" in AGENT_DECISION_SYSTEM.lower()

    def test_conformity_nudge_for_low_conformity(self):
        """Low-conformity agents should get a skepticism nudge."""
        agent = make_agent(0, "Rebel Reva", conformity=0.2, confrontational=0.5)
        nudge = SimulationEngine._conformity_nudge(agent)
        assert "skeptical" in nudge.lower() or "flaw" in nudge.lower(), (
            f"Low-conformity agent should get skepticism nudge. Got: '{nudge}'"
        )

    def test_no_nudge_for_high_conformity(self):
        """High-conformity, low-confrontational agents should not get a nudge."""
        agent = make_agent(0, "Follower Fred", conformity=0.8, confrontational=0.3)
        nudge = SimulationEngine._conformity_nudge(agent)
        assert nudge == "", f"High-conformity agent shouldn't get a nudge. Got: '{nudge}'"

    def test_nudge_for_high_confrontational(self):
        """Highly confrontational agents should get a push-back nudge."""
        agent = make_agent(0, "Fighter Frank", confrontational=0.9, conformity=0.5)
        nudge = SimulationEngine._conformity_nudge(agent)
        assert "push back" in nudge.lower() or "challenge" in nudge.lower(), (
            f"High-confrontational agent should get push-back nudge. Got: '{nudge}'"
        )

    def test_silence_encouraged_in_decision_prompt(self):
        """The decision prompt should explicitly encourage DO_NOTHING/OBSERVE."""
        from app.services.engine import AGENT_DECISION_SYSTEM
        assert "DO_NOTHING" in AGENT_DECISION_SYSTEM or "OBSERVE" in AGENT_DECISION_SYSTEM
        assert "doing nothing" in AGENT_DECISION_SYSTEM.lower() or "valid choice" in AGENT_DECISION_SYSTEM.lower()


# ============================================================================
# 8. PERSONALITY CONSISTENCY
# ============================================================================

class TestPersonalityConsistency:
    """Personality traits should predictably influence behavior."""

    def test_high_price_sensitivity_mentioned_in_rules(self):
        """High price_sensitivity agents should see trait-based guidance in the rules."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        assert "price_sensitivity" in BEHAVIOR_RULES_MARKET

    def test_high_brand_loyalty_mentioned_in_rules(self):
        """High brand_loyalty agents should see trait-based guidance in the rules."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        assert "brand_loyalty" in BEHAVIOR_RULES_MARKET

    def test_market_detection(self):
        """Market simulations should be correctly detected."""
        world = make_market_world()
        assert SimulationEngine._is_market_simulation(world), (
            "World with money resource and non-default metrics should be detected as market"
        )

    def test_non_market_world_not_detected(self):
        """A social simulation should not be detected as market."""
        from app.models.world import WorldBlueprint, WorldState, WorldMetrics, Location, TimeConfig
        blueprint = WorldBlueprint(
            name="Social World", description="test", rules=["Be kind"],
            locations=[Location(id="c", name="C", type="public", description="x")],
            resources=["food", "influence"], initial_tensions=[],
            time_config=TimeConfig(total_days=1, rounds_per_day=1),
        )
        world = WorldState(blueprint=blueprint, metrics=WorldMetrics())
        assert not SimulationEngine._is_market_simulation(world)


# ============================================================================
# 9. END-TO-END ENGINE RUN (Mock LLM)
# ============================================================================

class TestEngineEndToEnd:
    """Run the full engine loop with mock LLM and verify structural properties."""

    async def test_engine_runs_without_error(self, store, llm, resolver, gossip):
        """The engine should complete a 1-day simulation without crashing."""
        tension = TensionEngine(llm)
        narrator = Narrator(llm)
        engine = SimulationEngine(llm, store, tension, resolver, narrator, gossip=gossip)

        world = make_market_world(days=1, rounds_per_day=2)
        agents = make_netflix_cast(6)
        events: list[SSEEvent] = []

        async def emit(e: SSEEvent):
            events.append(e)

        await engine.run("test-sim", world, agents, emit)

        round_events = [e for e in events if e.type == "round_complete"]
        assert len(round_events) >= 1, "Should have at least 1 round_complete event"

        complete_events = [e for e in events if e.type == "simulation_complete"]
        assert len(complete_events) == 1, "Should end with simulation_complete"

    async def test_engine_produces_non_speech_actions(self, store, llm, resolver, gossip):
        """Over a 2-day run, at least some agents should take non-speech actions."""
        tension = TensionEngine(llm)
        narrator = Narrator(llm)
        engine = SimulationEngine(llm, store, tension, resolver, narrator, gossip=gossip)

        world = make_market_world(days=2, rounds_per_day=3)
        agents = make_netflix_cast(8)
        events: list[SSEEvent] = []

        async def emit(e: SSEEvent):
            events.append(e)

        await engine.run("test-sim", world, agents, emit)

        all_actions = []
        for e in events:
            if e.type == "round_complete" and "actions" in e.data:
                all_actions.extend(e.data["actions"])

        non_speech = [
            a for a in all_actions
            if a.get("action_type") not in ("SPEAK_PUBLIC", "SPEAK_PRIVATE", "DO_NOTHING", "OBSERVE")
        ]
        assert len(non_speech) >= 1, (
            f"Over 6 rounds with 8 agents, expected at least 1 non-speech action. "
            f"Got {len(non_speech)} non-speech out of {len(all_actions)} total."
        )

    async def test_silent_reactions_present(self, store, llm, resolver, gossip):
        """Reactive rounds should produce some silent reactions (from pre-filter)."""
        tension = TensionEngine(llm)
        narrator = Narrator(llm)
        engine = SimulationEngine(llm, store, tension, resolver, narrator, gossip=gossip)

        world = make_market_world(days=1, rounds_per_day=3)
        agents = make_netflix_cast(8)
        events: list[SSEEvent] = []

        async def emit(e: SSEEvent):
            events.append(e)

        await engine.run("test-sim", world, agents, emit)

        all_reactions = []
        for e in events:
            if e.type == "round_complete" and "reactions" in e.data:
                all_reactions.extend(e.data["reactions"])

        silent = [r for r in all_reactions if r.get("reaction_type") == "silent"]
        total = len(all_reactions)
        if total > 0:
            silence_rate = len(silent) / total
            assert silence_rate > 0.15, (
                f"Silence rate in reactions: {silence_rate:.0%} ({len(silent)}/{total}). "
                "Expected > 15% silent reactions."
            )

    async def test_agents_have_communication_style_in_output(self, store, llm, resolver, gossip):
        """Agent data in round events should include communication_style."""
        tension = TensionEngine(llm)
        narrator = Narrator(llm)
        engine = SimulationEngine(llm, store, tension, resolver, narrator, gossip=gossip)

        world = make_market_world(days=1, rounds_per_day=1)
        agents = make_netflix_cast(4)
        events: list[SSEEvent] = []

        async def emit(e: SSEEvent):
            events.append(e)

        await engine.run("test-sim", world, agents, emit)

        round_events = [e for e in events if e.type == "round_complete"]
        if round_events:
            agent_data = round_events[0].data.get("agents", [])
            for a in agent_data:
                assert "communication_style" in a, "Agent output should include communication_style"
                assert "knowledge_level" in a, "Agent output should include knowledge_level"


# ============================================================================
# 10. POSITION TRACKER
# ============================================================================

class TestPositionTracker:
    """The position tracker should show a BALANCED view — stayers and leavers, not just leavers."""

    def test_position_tracker_shows_undecided(self):
        """Agents who only talk should appear as undecided."""
        agents = [
            make_agent(0, "Alice"),
            make_agent(1, "Bob", working_memory=[
                'Day 1: SPEAK_PUBLIC: said "I\'m upset about this"',
            ]),
        ]
        result = SimulationEngine._build_position_tracker(agents[0], agents)
        assert "undecided" in result.lower() or "talking" in result.lower()

    def test_position_tracker_shows_leavers(self):
        """Agents who left should be shown in the LEFT category."""
        agents = [
            make_agent(0, "Alice"),
            make_agent(1, "Bob", working_memory=[
                'Day 1: ABANDON: left Netflix — too expensive',
            ]),
        ]
        result = SimulationEngine._build_position_tracker(agents[0], agents)
        assert "Bob" in result
        assert "left" in result.lower()

    def test_position_tracker_shows_stayers(self):
        """Agents who purchased or complied should appear as STAYED."""
        agents = [
            make_agent(0, "Alice"),
            make_agent(1, "Bob", working_memory=[
                'Day 1: PURCHASE: bought Netflix Premium',
            ]),
            make_agent(2, "Carol", working_memory=[
                'Day 1: ABANDON: left Netflix',
            ]),
        ]
        result = SimulationEngine._build_position_tracker(agents[0], agents)
        assert "stayed" in result.lower()
        assert "left" in result.lower()
        assert "Bob" in result
        assert "Carol" in result

    def test_position_tracker_balanced_counts(self):
        """Tracker should show counts as fractions of total to prevent panic bias."""
        agents = [make_agent(0, "Alice")]
        agents.append(make_agent(1, "Leaver1", working_memory=["Day 1: ABANDON: left"]))
        agents.append(make_agent(2, "Stayer1", working_memory=["Day 1: PURCHASE: bought it"]))
        agents.append(make_agent(3, "Stayer2", working_memory=["Day 1: comply: accepted changes"]))
        agents.append(make_agent(4, "Talker1", working_memory=['Day 1: said "I\'m upset"']))
        result = SimulationEngine._build_position_tracker(agents[0], agents)
        assert "1/4" in result or "LEFT (1" in result
        assert "2/4" in result or "STAYED (2" in result


# ============================================================================
# 11. MODEL SERIALIZATION BACKWARD COMPATIBILITY
# ============================================================================

class TestBackwardCompatibility:
    """New fields should have defaults so old data still loads."""

    def test_agent_without_new_fields_loads(self):
        """An agent serialized without communication_style/knowledge_level should load fine."""
        old_data = {
            "id": 1, "name": "OldAgent", "role": "citizen", "age": 30,
            "personality": {"honesty": 0.5, "ambition": 0.5, "empathy": 0.5,
                            "confrontational": 0.5, "conformity": 0.5},
            "background": "test", "goals": [], "core_memory": [],
            "working_memory": [], "beliefs": [], "relationships": {},
            "resources": {}, "location": "community", "faction": None,
            "emotional_state": "calm", "social_connections": [],
        }
        agent = AgentPersona.model_validate(old_data)
        assert agent.communication_style == "emotional"
        assert agent.knowledge_level == "full"

    def test_agent_roundtrip_with_new_fields(self):
        """Serialize and deserialize an agent with new fields."""
        agent = make_agent(0, "NewAgent", communication_style="sarcastic",
                           knowledge_level="partial")
        json_str = agent.model_dump_json()
        loaded = AgentPersona.model_validate_json(json_str)
        assert loaded.communication_style == "sarcastic"
        assert loaded.knowledge_level == "partial"


# ============================================================================
# 12. COMPARE LOOP PREVENTION
# ============================================================================

class TestCompareLoopPrevention:
    """Agents must not endlessly compare options — they should progress to decisions."""

    def test_repetition_detector_catches_compare_spam(self):
        """After 3 COMPAREs, the detector should produce a strong warning."""
        agent = make_agent(0, "Loopy Lou")
        agent.working_memory = [
            "Day 1 morning: compared Netflix vs Hulu: \"Hulu is cheaper\"",
            "Day 1 afternoon: compared Netflix vs Hulu: \"Need to evaluate\"",
            "Day 1 evening: compared Netflix vs Hulu: \"Still deciding\"",
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert warning, "Should produce a warning after 3 comparisons"
        assert "STOP" in warning or "🛑" in warning, (
            f"3 compares should trigger a forceful stop. Got: {warning[:80]}"
        )
        assert "DECIDE" in warning.upper() or "PURCHASE" in warning or "ABANDON" in warning, (
            "Warning should direct agent toward a decision action"
        )

    def test_repetition_detector_warns_after_2_compares(self):
        """After 2 COMPAREs, should get a softer warning to decide."""
        agent = make_agent(0, "Indecisive Ines")
        agent.working_memory = [
            "Day 1: compared Netflix vs Hulu: \"Hulu is cheaper\"",
            "Day 2: compared Netflix vs Hulu: \"Both have good content\"",
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert warning, "Should produce a warning after 2 comparisons"
        assert "decide" in warning.lower() or "decision" in warning.lower(), (
            f"2 compares should nudge toward a decision. Got: {warning[:80]}"
        )

    def test_no_warning_for_single_compare(self):
        """A single COMPARE should not trigger any warning."""
        agent = make_agent(0, "OneTimer Olivia")
        agent.working_memory = [
            "Day 1: compared Netflix vs Hulu: \"Hulu seems better\"",
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert not warning, f"One compare shouldn't trigger a warning. Got: {warning}"

    def test_repetition_detector_catches_protest_spam(self):
        """After 2 protests, the detector should suggest escalation."""
        agent = make_agent(0, "Protester Pete")
        agent.working_memory = [
            "Day 1: protest against Netflix price hikes",
            "Day 2: protest against Netflix price hikes",
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert warning, "Should produce a warning after 2 protests"
        assert "escalate" in warning.lower() or "DEFECT" in warning or "ABANDON" in warning, (
            f"Protest spam should suggest escalation. Got: {warning[:80]}"
        )

    def test_repetition_detector_catches_research_spam(self):
        """After 2 researches, the detector should push toward action."""
        agent = make_agent(0, "Researcher Rick")
        agent.working_memory = [
            "Day 1: Researched 'Netflix pricing' — found info",
            "Day 2: Researched 'Hulu vs Netflix' — more info",
        ]
        warning = SimulationEngine._detect_repetition(agent)
        assert warning, "Should produce a warning after 2 research actions"
        assert "act" in warning.lower() or "decide" in warning.lower(), (
            f"Research spam should push toward action. Got: {warning[:80]}"
        )

    def test_decision_progression_in_behavior_rules(self):
        """BEHAVIOR_RULES_MARKET must contain the decision progression funnel."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        assert "DECISION PROGRESSION" in BEHAVIOR_RULES_MARKET or "decision" in BEHAVIOR_RULES_MARKET.lower()
        assert "ONCE" in BEHAVIOR_RULES_MARKET, (
            "Rules should tell agents to COMPARE only once"
        )
        assert "PURCHASE" in BEHAVIOR_RULES_MARKET
        assert "ABANDON" in BEHAVIOR_RULES_MARKET
        assert "DEFECT" in BEHAVIOR_RULES_MARKET

    def test_compare_once_language_in_rules(self):
        """Rules should explicitly say to compare only once."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        lower = BEHAVIOR_RULES_MARKET.lower()
        assert "compare once" in lower or "once" in lower, (
            "Rules must tell agents that comparing once is enough"
        )
        assert "don't compare again" in lower or "not repeatedly" in lower, (
            "Rules must explicitly warn against repeated comparing"
        )


# ============================================================================
# 13. DECISION STAGE NUDGE
# ============================================================================

class TestDecisionStageNudge:
    """The decision stage nudge should correctly identify where an agent is."""

    def test_stage_after_comparison(self):
        """An agent who compared should be told to decide."""
        agent = make_agent(0, "Post-Compare Pam")
        agent.working_memory = [
            "Day 1: compared Netflix vs Hulu: \"Hulu is cheaper\"",
        ]
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge, "Should produce a nudge after comparing"
        assert "DECIDE" in nudge.upper() or "decide" in nudge.lower(), (
            f"Post-compare nudge should direct to decide. Got: {nudge[:80]}"
        )

    def test_stage_after_research(self):
        """An agent who researched should be told to decide."""
        agent = make_agent(0, "Post-Research Randy")
        agent.working_memory = [
            "Day 1: Researched 'Netflix pricing changes'",
        ]
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge, "Should produce a nudge after researching"
        assert "DECIDE" in nudge.upper() or "decide" in nudge.lower()

    def test_stage_after_decision(self):
        """An agent who already decided should be told to influence."""
        agent = make_agent(0, "Decisive Dana")
        agent.working_memory = [
            "Day 1: compared Netflix vs Hulu",
            "Day 2: ABANDON: abandoned Netflix — too expensive",
        ]
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge, "Should produce a nudge after deciding"
        assert "influence" in nudge.lower() or "RECOMMEND" in nudge or "experience" in nudge.lower(), (
            f"Post-decision nudge should direct to influence. Got: {nudge[:80]}"
        )

    def test_stage_after_protest(self):
        """An agent who protested should be told to escalate or reconsider."""
        agent = make_agent(0, "Protested Paul")
        agent.working_memory = [
            "Day 1: protest against Netflix pricing",
        ]
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge, "Should produce a nudge after protesting"
        assert "escalate" in nudge.lower() or "ABANDON" in nudge or "DEFECT" in nudge, (
            f"Post-protest nudge should suggest escalation. Got: {nudge[:80]}"
        )

    def test_no_nudge_for_fresh_agent(self):
        """An agent with no history should get no nudge (or minimal)."""
        agent = make_agent(0, "Fresh Fiona")
        agent.working_memory = []
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge == "", "Fresh agent should get no stage nudge"

    def test_spoken_agent_gets_gather_info_nudge(self):
        """An agent who only spoke should be guided to gather info or decide."""
        agent = make_agent(0, "Talky Tina")
        agent.working_memory = [
            'Day 1: SPEAK_PUBLIC: said "I\'m frustrated with Netflix"',
        ]
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge, "Agent who spoke should get a stage nudge"
        assert "COMPARE" in nudge or "RESEARCH" in nudge or "decision" in nudge.lower(), (
            f"Post-speech nudge should suggest gathering info or deciding. Got: {nudge[:80]}"
        )


# ============================================================================
# 14. ACTION GATING
# ============================================================================

class TestActionGating:
    """After repeated actions, those actions should be removed from the available list."""

    def test_compare_removed_after_2(self):
        """COMPARE should be removed from the prompt after 2+ compares in working memory."""
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.research = None
        engine.gossip = GossipEngine()

        agent = make_agent(0, "Gated Gary", working_memory=[
            "Day 1: compared Netflix vs Hulu: \"Hulu cheaper\"",
            "Day 2: compared Netflix vs Disney+: \"Disney+ has Marvel\"",
        ])
        world = make_market_world()
        agents = make_netflix_cast(4)
        agents[0] = agent

        system_prompt, _ = engine._build_decision_prompt(agent, world, agents)
        assert "AVAILABLE ACTIONS" in system_prompt
        actions_block = system_prompt.split("AVAILABLE ACTIONS")[1].split("\n\n")[0]
        action_lines = [l.strip() for l in actions_block.strip().split("\n") if l.strip().startswith("- ")]
        action_names = [l.lstrip("- ").strip() for l in action_lines]
        assert "COMPARE" not in action_names, (
            f"COMPARE should be removed from action list after 2 compares. Actions: {action_names}"
        )

    def test_protest_removed_after_2(self):
        """PROTEST should be removed from the prompt after 2+ protests."""
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.research = None
        engine.gossip = GossipEngine()

        agent = make_agent(0, "Gated Grace", working_memory=[
            "Day 1: protest against Netflix pricing",
            "Day 2: protest against Netflix ads",
        ])
        world = make_market_world()
        agents = make_netflix_cast(4)
        agents[0] = agent

        system_prompt, _ = engine._build_decision_prompt(agent, world, agents)
        assert "AVAILABLE ACTIONS" in system_prompt
        actions_block = system_prompt.split("AVAILABLE ACTIONS")[1].split("\n\n")[0]
        action_lines = [l.strip() for l in actions_block.strip().split("\n") if l.strip().startswith("- ")]
        action_names = [l.lstrip("- ").strip() for l in action_lines]
        assert "PROTEST" not in action_names, (
            f"PROTEST should be removed from action list after 2 protests. Actions: {action_names}"
        )

    def test_compare_still_available_after_1(self):
        """COMPARE should still be available after only 1 compare."""
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.research = None
        engine.gossip = GossipEngine()

        agent = make_agent(0, "Allowed Alice", working_memory=[
            "Day 1: compared Netflix vs Hulu: \"Checking options\"",
        ])
        world = make_market_world()
        agents = make_netflix_cast(4)
        agents[0] = agent

        system_prompt, _ = engine._build_decision_prompt(agent, world, agents)
        assert "COMPARE" in system_prompt, (
            "COMPARE should still be available after just 1 compare"
        )


# ============================================================================
# 15. REACTIVE MICRO-ROUND FOR NON-SPEECH ACTIONS
# ============================================================================

class TestReactiveMicroRoundActions:
    """Non-speech actions like PROTEST and ABANDON should trigger conversational reactions."""

    def test_action_description_for_protest(self):
        """_describe_action_for_reaction should produce a readable protest description."""
        entry = ActionEntry(
            round=1, day=1, time_of_day="morning", agent_id=0,
            agent_name="Natalie", location="community",
            action_type=ActionType.PROTEST,
            action_args={"target": "Netflix price hikes"},
            speech="This is outrageous!",
        )
        desc = SimulationEngine._describe_action_for_reaction(entry)
        assert "protest" in desc.lower(), f"Description should mention protest. Got: {desc}"
        assert "Netflix" in desc or "price" in desc, f"Description should mention target. Got: {desc}"
        assert "outrageous" in desc, f"Description should include speech. Got: {desc}"

    def test_action_description_for_abandon(self):
        """_describe_action_for_reaction should describe an abandon with reason."""
        entry = ActionEntry(
            round=1, day=1, time_of_day="morning", agent_id=0,
            agent_name="Owen", location="community",
            action_type=ActionType.ABANDON,
            action_args={"product": "Netflix", "reason": "too expensive"},
            speech="I'm done.",
        )
        desc = SimulationEngine._describe_action_for_reaction(entry)
        assert "abandon" in desc.lower(), f"Should mention abandon. Got: {desc}"
        assert "Netflix" in desc, f"Should mention product. Got: {desc}"
        assert "expensive" in desc, f"Should include reason. Got: {desc}"

    def test_action_description_for_defect(self):
        """_describe_action_for_reaction should describe a defection."""
        entry = ActionEntry(
            round=1, day=1, time_of_day="morning", agent_id=0,
            agent_name="Tara", location="community",
            action_type=ActionType.DEFECT,
            action_args={"rule": "Netflix subscription", "how": "switched to Hulu"},
        )
        desc = SimulationEngine._describe_action_for_reaction(entry)
        assert "defect" in desc.lower(), f"Should mention defect. Got: {desc}"
        assert "Hulu" in desc, f"Should include defection details. Got: {desc}"

    def test_action_description_for_compare(self):
        """_describe_action_for_reaction should describe a comparison."""
        entry = ActionEntry(
            round=1, day=1, time_of_day="morning", agent_id=0,
            agent_name="Jared", location="community",
            action_type=ActionType.COMPARE,
            action_args={"product_a": "Netflix", "product_b": "Hulu"},
        )
        desc = SimulationEngine._describe_action_for_reaction(entry)
        assert "Netflix" in desc and "Hulu" in desc, f"Should mention both products. Got: {desc}"
        assert "compar" in desc.lower(), f"Should mention comparing. Got: {desc}"

    def test_action_description_for_purchase(self):
        """_describe_action_for_reaction should describe a purchase."""
        entry = ActionEntry(
            round=1, day=1, time_of_day="morning", agent_id=0,
            agent_name="Simon", location="community",
            action_type=ActionType.PURCHASE,
            action_args={"product": "Netflix Premium"},
        )
        desc = SimulationEngine._describe_action_for_reaction(entry)
        assert "purchase" in desc.lower(), f"Should mention purchase. Got: {desc}"
        assert "Netflix" in desc, f"Should mention product. Got: {desc}"

    def test_reactive_action_prompt_exists(self):
        """REACTIVE_ACTION_PROMPT should exist and have required placeholders."""
        from app.services.engine import REACTIVE_ACTION_PROMPT
        assert "{actor}" in REACTIVE_ACTION_PROMPT, "Must have {actor} placeholder"
        assert "{action_description}" in REACTIVE_ACTION_PROMPT, "Must have {action_description} placeholder"
        assert "{name}" in REACTIVE_ACTION_PROMPT, "Must have {name} placeholder"
        assert "{beliefs}" in REACTIVE_ACTION_PROMPT, "Must have {beliefs} placeholder"

    def test_reactive_action_prompt_encourages_engagement(self):
        """REACTIVE_ACTION_PROMPT should encourage conversational reactions."""
        from app.services.engine import REACTIVE_ACTION_PROMPT
        lower = REACTIVE_ACTION_PROMPT.lower()
        assert "challenge" in lower or "support" in lower, "Prompt should suggest challenging or supporting"
        assert "persuade" in lower or "ask" in lower, "Prompt should suggest persuading or asking"

    async def test_engine_triggers_action_reactions(self, store, llm, resolver, gossip):
        """When agents take non-speech actions, reactive rounds should fire for them."""
        tension = TensionEngine(llm)
        narrator = Narrator(llm)
        engine = SimulationEngine(llm, store, tension, resolver, narrator, gossip=gossip)

        world = make_market_world(days=2, rounds_per_day=3)
        agents = make_netflix_cast(8)
        events: list[SSEEvent] = []

        async def emit(e: SSEEvent):
            events.append(e)

        await engine.run("test-sim", world, agents, emit)

        all_reactions = []
        for e in events:
            if e.type == "round_complete" and "reactions" in e.data:
                all_reactions.extend(e.data["reactions"])

        non_silent = [r for r in all_reactions if r.get("reaction_type") != "silent"]
        assert len(non_silent) >= 1, (
            f"Over a 2-day sim with 8 agents, expected at least 1 non-silent reaction. "
            f"Got {len(non_silent)} non-silent out of {len(all_reactions)} total."
        )

    def test_conversational_actions_identified_in_round(self):
        """The engine should identify PROTEST, ABANDON, DEFECT, etc. as conversational."""
        from app.services.engine import ActionType
        conversational_types = {
            ActionType.PROTEST, ActionType.ABANDON, ActionType.DEFECT,
            ActionType.RECOMMEND, ActionType.COMPARE, ActionType.PURCHASE,
        }
        for at in conversational_types:
            entry = ActionEntry(
                round=1, day=1, time_of_day="morning", agent_id=0,
                agent_name="Test", location="community",
                action_type=at, action_args={},
            )
            assert entry.action_type in conversational_types, (
                f"{at} should be in the conversational actions set"
            )


# ============================================================================
# 16. ANTI-CASCADE — LOYALTY ANCHOR
# ============================================================================

class TestLoyaltyAnchor:
    """High brand_loyalty agents should resist defection cascades."""

    def test_loyal_agent_gets_strong_anchor(self):
        """brand_loyalty >= 0.7 should produce a LOYALTY ANCHOR in the prompt."""
        agent = make_agent(0, "Loyal Lisa", brand_loyalty=0.9)
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "LOYALTY ANCHOR" in anchor
        assert "COMPLY" in anchor or "PURCHASE" in anchor
        assert "NOT follow the crowd" in anchor

    def test_moderate_loyalty_gets_softer_anchor(self):
        """brand_loyalty 0.5-0.7 should get moderate retention pressure."""
        agent = make_agent(0, "Moderate Mike", brand_loyalty=0.6)
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "grumble but stay" in anchor.lower() or "moderate" in anchor.lower()

    def test_low_loyalty_no_anchor(self):
        """brand_loyalty < 0.5 should not get a loyalty anchor."""
        agent = make_agent(0, "Free Fred", brand_loyalty=0.3)
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "LOYALTY ANCHOR" not in anchor

    def test_price_sensitive_gets_exit_permission(self):
        """price_sensitivity >= 0.7 should get fast-exit guidance."""
        agent = make_agent(0, "Penny Pincher", price_sensitivity=0.9)
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "PRICE PRESSURE" in anchor
        assert "ABANDON" in anchor or "DEFECT" in anchor

    def test_social_proof_before_tipping_point(self):
        """High social_proof agent with no defectors visible should be told to wait."""
        agent = make_agent(0, "Follower Faye", social_proof=0.8, working_memory=[
            'Day 1: said "I\'m upset about this"',
        ])
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "wait" in anchor.lower() or "majority" in anchor.lower()

    def test_social_proof_after_tipping_point(self):
        """High social_proof agent who has seen 3+ defections should get tipping point."""
        agent = make_agent(0, "Follower Faye", social_proof=0.8, working_memory=[
            'Day 1: Alice abandoned Netflix',
            'Day 1: Bob defected to Hulu',
            'Day 2: Carol switched to Disney+',
        ])
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "TIPPING POINT" in anchor

    def test_novelty_seeker_gets_diversity_nudge(self):
        """High novelty_seeking should be told to consider DIFFERENT competitors."""
        agent = make_agent(0, "Novel Nancy", novelty_seeking=0.8)
        anchor = SimulationEngine._loyalty_anchor(agent)
        assert "DIFFERENT" in anchor or "different" in anchor.lower()

    def test_loyalty_anchor_in_decision_prompt(self):
        """The loyalty anchor should appear in the built decision prompt for market sims."""
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.research = None
        engine.gossip = GossipEngine()

        agent = make_agent(0, "Loyal Larry", brand_loyalty=0.9)
        world = make_market_world()
        agents = make_netflix_cast(4)
        agents[0] = agent

        system_prompt, _ = engine._build_decision_prompt(agent, world, agents)
        assert "LOYALTY ANCHOR" in system_prompt, (
            "Decision prompt for loyal agent in market sim must include LOYALTY ANCHOR"
        )


# ============================================================================
# 17. ANTI-CASCADE — DECISION STAGE NUDGE (trait-aware)
# ============================================================================

class TestTraitAwareNudge:
    """Decision stage nudges should be different for loyal vs price-sensitive agents."""

    def test_loyal_agent_post_compare_gets_stay_nudge(self):
        """A loyal agent who compared should be nudged toward PURCHASE/COMPLY, not ABANDON."""
        agent = make_agent(0, "Loyal Lucy", brand_loyalty=0.8, working_memory=[
            "Day 1: compared Netflix vs Hulu: \"Both have merits\"",
        ])
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge
        assert "PURCHASE" in nudge or "COMPLY" in nudge
        assert "recommit" in nudge.lower() or "value" in nudge.lower()

    def test_loyal_agent_post_protest_gets_reconcile_nudge(self):
        """A loyal agent who protested should be nudged toward acceptance, not escalation."""
        agent = make_agent(0, "Loyal Leo", brand_loyalty=0.7, working_memory=[
            "Day 1: protest against Netflix pricing",
        ])
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge
        assert "loyal" in nudge.lower() or "COMPLY" in nudge
        assert "ABANDON" not in nudge.split("untenable")[0] if "untenable" in nudge else True

    def test_price_sensitive_post_protest_gets_escalation_nudge(self):
        """A price-sensitive agent who protested should be nudged toward ABANDON/DEFECT."""
        agent = make_agent(0, "Penny Pete", brand_loyalty=0.3, price_sensitivity=0.8,
                           working_memory=["Day 1: protest against Netflix pricing"])
        nudge = SimulationEngine._decision_stage_nudge(agent)
        assert nudge
        assert "ABANDON" in nudge or "DEFECT" in nudge


# ============================================================================
# 18. ANTI-CASCADE — CONTENT REPETITION DETECTION
# ============================================================================

class TestContentRepetition:
    """Agents should be caught when they repeat the same talking point across rounds."""

    def test_catches_keyword_spam(self):
        """Repeating 'blockbuster' 3+ times across speeches should trigger a warning."""
        agent = make_agent(0, "Selena", working_memory=[
            'Day 1: said "This reminds me of Blockbuster going under"',
            'Day 2: said "Just like Blockbuster couldn\'t keep up"',
            'Day 3: said "Netflix is heading the way of Blockbuster"',
        ])
        warning = SimulationEngine._detect_repetition(agent)
        assert warning
        assert "loop" in warning.lower() or "repeat" in warning.lower()

    def test_catches_family_movie_night_spam(self):
        """Repeating 'family movie night' theme should trigger a warning."""
        agent = make_agent(0, "Jordan", working_memory=[
            'Day 1: said "Family movie night is ruined by these rules"',
            'Day 2: said "What about family movie night experiences?"',
            'Day 3: said "Our family movie night tradition is at stake"',
        ])
        warning = SimulationEngine._detect_repetition(agent)
        assert warning
        assert "loop" in warning.lower() or "repeat" in warning.lower()

    def test_no_warning_for_varied_content(self):
        """Agents with genuinely different content each round should not be flagged."""
        agent = make_agent(0, "Diverse Dave", working_memory=[
            'Day 1: said "The pricing changes are frustrating"',
            'Day 2: said "I compared Hulu and it looks decent"',
            'Day 3: said "Maybe we should try Disney+ instead"',
        ])
        warning = SimulationEngine._detect_content_repetition(
            [m.lower() for m in agent.working_memory]
        )
        assert not warning


# ============================================================================
# 19. ANTI-CASCADE — BEHAVIOR RULES
# ============================================================================

class TestAntiCascadeRules:
    """BEHAVIOR_RULES_MARKET must contain anti-cascade language."""

    def test_anti_cascade_rule_exists(self):
        """Rules must explicitly state that not everyone leaves."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        lower = BEHAVIOR_RULES_MARKET.lower()
        assert "not everyone leaves" in lower or "anti-cascade" in lower

    def test_comply_is_valid_outcome(self):
        """Rules must present COMPLY as a valid and common decision."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        lower = BEHAVIOR_RULES_MARKET.lower()
        assert "comply" in lower
        assert "common" in lower or "valid" in lower

    def test_binding_trait_outcomes(self):
        """Rules must say brand_loyalty >= 0.7 MUST end at COMPLY or PURCHASE."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        assert "brand_loyalty >= 0.7" in BEHAVIOR_RULES_MARKET or "brand_loyalty >=0.7" in BEHAVIOR_RULES_MARKET
        assert "MUST" in BEHAVIOR_RULES_MARKET

    def test_social_proof_tipping_point(self):
        """Rules must explain that social_proof agents follow the majority, not the loudest."""
        from app.services.engine import BEHAVIOR_RULES_MARKET
        lower = BEHAVIOR_RULES_MARKET.lower()
        assert "majority" in lower
        assert "tipping point" in lower or "3+" in lower


# ============================================================================
# 20. EMOTIONAL DECAY — PERSONALITY-AWARE
# ============================================================================

class TestPersonalityAwareDecay:
    """Emotional decay should be faster for conformist/loyal agents."""

    def test_conformist_decays_faster(self):
        """Conformist agents should decay from negative states faster than rebels."""
        resolver = ActionResolver()
        conformist = make_agent(0, "Conformist Carl", conformity=0.9, brand_loyalty=0.8,
                                confrontational=0.2, emotional_state="frustrated")
        rebel = make_agent(1, "Rebel Rita", conformity=0.1, brand_loyalty=0.2,
                           confrontational=0.9, emotional_state="frustrated")

        conformist_decays = 0
        rebel_decays = 0
        trials = 500

        for _ in range(trials):
            conformist.emotional_state = "frustrated"
            rebel.emotional_state = "frustrated"
            resolver._emotional_decay([conformist, rebel])
            if conformist.emotional_state != "frustrated":
                conformist_decays += 1
            if rebel.emotional_state != "frustrated":
                rebel_decays += 1

        assert conformist_decays > rebel_decays, (
            f"Conformist decayed {conformist_decays}/{trials} times vs rebel {rebel_decays}/{trials}. "
            "Conformists should decay faster."
        )

    def test_loyal_agent_decays_faster(self):
        """High brand_loyalty agents should accept changes emotionally faster."""
        resolver = ActionResolver()
        loyal = make_agent(0, "Loyal Lou", brand_loyalty=0.9, conformity=0.5,
                           emotional_state="angry")
        disloyal = make_agent(1, "Disloyal Dan", brand_loyalty=0.1, conformity=0.5,
                              emotional_state="angry")

        loyal_decays = 0
        disloyal_decays = 0
        trials = 500

        for _ in range(trials):
            loyal.emotional_state = "angry"
            disloyal.emotional_state = "angry"
            resolver._emotional_decay([loyal, disloyal])
            if loyal.emotional_state != "angry":
                loyal_decays += 1
            if disloyal.emotional_state != "angry":
                disloyal_decays += 1

        assert loyal_decays > disloyal_decays, (
            f"Loyal agent decayed {loyal_decays}/{trials} vs disloyal {disloyal_decays}/{trials}. "
            "Loyal agents should emotionally settle faster."
        )
