"""Shared fixtures for simulation realism tests.

The MockLLM returns deterministic but personality-aware responses so we can
test the *engine mechanics* (silence filters, repetition detection, emotional
contagion, knowledge diffusion, conversation threading) without hitting an
actual LLM.  For full end-to-end realism checks that exercise the LLM, run
with --live-llm (see pytest_addoption below).
"""
from __future__ import annotations
import json
import os
import random
import tempfile

import pytest
import pytest_asyncio

from app.models.agent import AgentPersona, Personality, SocialEdge, COMMUNICATION_STYLES
from app.models.world import (
    WorldBlueprint, WorldState, WorldMetrics, Location, TimeConfig,
)
from app.models.action import ActionType
from app.db.store import SimulationStore
from app.services.resolver import ActionResolver
from app.services.gossip import GossipEngine
from app.services.tension import TensionEngine
from app.services.narrator import Narrator
from app.services.engine import SimulationEngine


# ---------------------------------------------------------------------------
# CLI option for live-LLM tests
# ---------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--live-llm", action="store_true", default=False,
        help="Run tests that require a real LLM endpoint (slow, costs money)",
    )


# ---------------------------------------------------------------------------
# Mock LLM — deterministic, personality-aware
# ---------------------------------------------------------------------------
class MockLLM:
    """Returns canned responses that vary by personality traits embedded in the
    system prompt. Good enough to exercise the engine loop; not a substitute
    for real LLM quality tests."""

    def __init__(self):
        self.calls: list[dict] = []

    async def generate(
        self, system: str, user: str,
        json_mode: bool = False, max_tokens: int = 1000, retries: int = 3,
    ) -> str:
        self.calls.append({"system": system, "user": user, "json_mode": json_mode})
        if json_mode:
            return self._json_response(system, user)
        return self._text_response(system, user)

    async def generate_batch(
        self, prompts: list[tuple[str, str]],
        json_mode: bool = False, max_tokens: int = 1000,
    ) -> list[str]:
        return [
            await self.generate(s, u, json_mode=json_mode, max_tokens=max_tokens)
            for s, u in prompts
        ]

    async def generate_light(self, system: str, user: str, max_tokens: int = 100) -> str:
        return await self.generate(system, user, json_mode=False, max_tokens=max_tokens)

    def get_stats(self) -> dict:
        return {"total_tokens": 0, "total_calls": len(self.calls)}

    # -- response generators ------------------------------------------------

    def _json_response(self, system: str, user: str) -> str:
        if "What do you do?" in user or "AVAILABLE ACTIONS" in system:
            return self._decision_response(system)
        if "event" in system.lower() and "fate engine" in system.lower():
            return json.dumps({
                "event": "A competitor launches a flash 50% off sale",
                "resource_changes": {},
            })
        if "splinter" in system.lower():
            return json.dumps({
                "splinter_belief": "We should negotiate, not fight",
                "reason": "Some members prefer diplomacy",
            })
        if "Reflect" in system:
            return json.dumps({
                "core_memory": ["Things are changing"],
                "beliefs": ["Change is inevitable"],
                "goals": ["Adapt"],
            })
        if "narrate" in system.lower() or "narrator" in system.lower():
            return '""'
        return "{}"

    def _decision_response(self, system: str) -> str:
        sys_lower = system.lower()
        action = "SPEAK_PUBLIC"
        speech = "I have thoughts about this."
        args: dict = {}

        if "price_sensitivity=0.9" in system or "price_sensitivity=1.0" in system:
            action = random.choice(["ABANDON", "COMPARE", "SPEAK_PUBLIC"])
            if action == "ABANDON":
                args = {"product": "Netflix", "reason": "Too expensive"}
                speech = "I'm done paying this much."
            elif action == "COMPARE":
                args = {"product_a": "Netflix", "product_b": "Hulu", "verdict": "Hulu is cheaper"}
                speech = "Let me compare the options."
        elif "brand_loyalty=0.9" in system or "brand_loyalty=1.0" in system:
            action = random.choice(["PURCHASE", "SPEAK_PUBLIC", "COMPLY"])
            if action == "PURCHASE":
                args = {"product": "Netflix Premium", "amount": 20}
                speech = "Still worth it."
            elif action == "COMPLY":
                args = {}
                speech = None
        elif "STOP TALKING" in system:
            action = random.choice(["ABANDON", "COMPARE", "RESEARCH", "PROTEST"])
            args = {"product": "Netflix", "reason": "Forced to act"}
            speech = "Fine, I'll do something."
        elif "novelty_seeking=0.9" in system or "novelty_seeking=0.8" in system:
            action = "RESEARCH"
            args = {"query": "streaming alternatives 2024", "reason": "Looking for better options"}
            speech = None
        elif random.random() < 0.3:
            action = "DO_NOTHING"
            speech = None
            args = {}
        elif random.random() < 0.15:
            action = "OBSERVE"
            speech = None
            args = {}

        return json.dumps({
            "feel": "frustrated" if "price" in sys_lower else "curious",
            "want": "to make a decision",
            "fear": "missing out",
            "action": action,
            "args": args,
            "speech": speech,
            "internal_thought": "thinking...",
            "belief_updates": [],
            "memory_promotion": None,
        })

    def _text_response(self, system: str, user: str) -> str:
        if "React" in user or "react" in system.lower():
            if random.random() < 0.5:
                return "c"
            return random.choice([
                'a That doesn\'t add up for me.',
                'a Has anyone actually checked the competitor prices?',
                'b I\'m not sure about this.',
                'a My cousin cancelled last month and doesn\'t miss it.',
                'c',
            ])
        if "summarize" in system.lower() or "narrat" in system.lower():
            return "Agents discussed the situation. Some acted, some didn't."
        return "I see."


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------
STYLE_NAMES = list(COMMUNICATION_STYLES.keys())


def make_agent(
    id: int, name: str, *,
    role: str = "subscriber",
    brand_loyalty: float = 0.5,
    price_sensitivity: float = 0.5,
    social_proof: float = 0.5,
    novelty_seeking: float = 0.5,
    confrontational: float = 0.5,
    conformity: float = 0.5,
    empathy: float = 0.5,
    ambition: float = 0.5,
    honesty: float = 0.5,
    communication_style: str | None = None,
    knowledge_level: str = "full",
    emotional_state: str = "calm",
    beliefs: list[str] | None = None,
    working_memory: list[str] | None = None,
    social_connections: list[SocialEdge] | None = None,
) -> AgentPersona:
    return AgentPersona(
        id=id,
        name=name,
        role=role,
        age=30,
        personality=Personality(
            honesty=honesty,
            ambition=ambition,
            empathy=empathy,
            confrontational=confrontational,
            conformity=conformity,
            brand_loyalty=brand_loyalty,
            price_sensitivity=price_sensitivity,
            social_proof=social_proof,
            novelty_seeking=novelty_seeking,
        ),
        background=f"{name} is a {role}.",
        goals=["Decide what to do"],
        beliefs=beliefs or [],
        working_memory=working_memory or [],
        resources={"money": 50, "satisfaction": 50},
        location="community",
        emotional_state=emotional_state,
        communication_style=communication_style or random.choice(STYLE_NAMES),
        knowledge_level=knowledge_level,
        social_connections=social_connections or [],
    )


def make_netflix_cast(n: int = 10) -> list[AgentPersona]:
    """Diverse cast mimicking the Netflix Price Hike scenario."""
    agents = [
        make_agent(0, "Natalie", price_sensitivity=0.9, confrontational=0.8, conformity=0.2,
                   communication_style="emotional", beliefs=["Netflix is ripping us off"]),
        make_agent(1, "Simon", brand_loyalty=0.9, conformity=0.7, confrontational=0.3,
                   communication_style="verbose", beliefs=["Netflix is worth it for family time"]),
        make_agent(2, "Owen", price_sensitivity=0.6, social_proof=0.8, novelty_seeking=0.4,
                   communication_style="question-asker", beliefs=["I should compare options"]),
        make_agent(3, "Tara", price_sensitivity=0.8, empathy=0.7, ambition=0.3,
                   communication_style="anecdote-teller", beliefs=["Budgets are tight"]),
        make_agent(4, "Jared", brand_loyalty=0.6, confrontational=0.7, honesty=0.8,
                   communication_style="data-driven", beliefs=["Quality content matters"]),
        make_agent(5, "Rita", price_sensitivity=0.7, novelty_seeking=0.7,
                   communication_style="terse", beliefs=["There are better options"]),
        make_agent(6, "Maxwell", brand_loyalty=0.7, social_proof=0.6,
                   communication_style="passive-aggressive", beliefs=["Netflix used to be great"]),
        make_agent(7, "Evelyn", empathy=0.8, conformity=0.6, ambition=0.2,
                   communication_style="emotional", beliefs=["Entertainment should be affordable"]),
        make_agent(8, "Carlito", price_sensitivity=0.9, social_proof=0.7,
                   communication_style="sarcastic", beliefs=["Companies only care about profit"]),
        make_agent(9, "Samantha", social_proof=0.8, confrontational=0.5,
                   communication_style="verbose", beliefs=["Loyal subscribers deserve better"]),
    ]
    for i, a in enumerate(agents):
        connections = []
        for j in range(n):
            if i != j:
                connections.append(SocialEdge(
                    target_id=j,
                    strength=round(random.uniform(0.3, 0.8), 2),
                    sentiment=round(random.uniform(-0.2, 0.3), 2),
                ))
        a.social_connections = connections
    return agents[:n]


# ---------------------------------------------------------------------------
# World / store fixtures
# ---------------------------------------------------------------------------
def make_market_world(days: int = 2, rounds_per_day: int = 3) -> WorldState:
    blueprint = WorldBlueprint(
        name="Netflix Price Hike",
        description="Netflix raises prices by 40% and adds ads to the basic tier.",
        rules=[
            "Netflix dominates streaming with 200M+ subscribers.",
            "Netflix raises prices by 40% while adding ads to the basic tier.",
            "Competitors include Disney+, HBO Max, Hulu, and Apple TV+.",
            "Customers are price-sensitive but habit-driven.",
        ],
        locations=[Location(id="community", name="Community", type="public", description="shared space")],
        resources=["money", "satisfaction", "loyalty_points"],
        initial_tensions=["price increase vs value", "ads vs ad-free experience"],
        time_config=TimeConfig(
            total_days=days,
            rounds_per_day=rounds_per_day,
            active_agents_per_round_min=4,
            active_agents_per_round_max=8,
        ),
    )
    return WorldState(
        blueprint=blueprint,
        metrics=WorldMetrics(
            brand_sentiment=0.6,
            purchase_intent=0.5,
            churn_risk=0.3,
            adoption_rate=0.7,
        ),
    )


@pytest_asyncio.fixture
async def store(tmp_path):
    s = SimulationStore(str(tmp_path))
    await s.init()
    await s.create("test-sim", "Netflix Price Hike test")
    return s


@pytest.fixture
def llm():
    return MockLLM()


@pytest.fixture
def resolver():
    return ActionResolver()


@pytest.fixture
def gossip():
    return GossipEngine()
