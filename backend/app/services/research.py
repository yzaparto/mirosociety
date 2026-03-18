from __future__ import annotations
import asyncio
import logging

from duckduckgo_search import DDGS

from app.models.agent import AgentPersona
from app.models.world import WorldState
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)

RESEARCH_SUMMARIZE_SYSTEM = """You are {name}, a {age}-year-old {role}.
Personality: honesty={honesty:.1f}, ambition={ambition:.1f}, empathy={empathy:.1f}, conformity={conformity:.1f}
{market_personality}

Your current beliefs:
{beliefs}

You just searched the internet for: "{query}"
Reason: {reason}

Here are the search results:
{search_results}

Based on YOUR personality and beliefs, what do you take away from this?
Write 2-3 sentences of what you learned and how it affects your thinking.
Be specific — cite numbers, names, or facts you found.
If the results contradict your beliefs, note the tension.
If they confirm your beliefs, note the reinforcement."""


class ResearchService:
    def __init__(self, llm: LLMClient, enabled: bool = True, max_per_round: int = 5):
        self.llm = llm
        self.enabled = enabled
        self.max_per_round = max_per_round

    async def _raw_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Run a DuckDuckGo search in a thread pool to avoid blocking the event loop."""
        def _search():
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            except Exception as e:
                logger.warning("DuckDuckGo search failed for '%s': %s", query, e)
                return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _search)

    async def search_and_summarize(
        self,
        query: str,
        reason: str,
        agent: AgentPersona,
        world_state: WorldState,
    ) -> str:
        if not self.enabled:
            return ""

        results = await self._raw_search(query)
        if not results:
            return ""

        snippets = []
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            snippets.append(f"{i}. {title}\n   {body}\n   Source: {href}")

        search_results_text = "\n\n".join(snippets)

        p = agent.personality
        market_personality = ""
        has_market_traits = (
            p.brand_loyalty != 0.5 or p.price_sensitivity != 0.5
            or p.social_proof != 0.5 or p.novelty_seeking != 0.5
        )
        if has_market_traits:
            market_personality = (
                f"Consumer traits: brand_loyalty={p.brand_loyalty:.1f}, "
                f"price_sensitivity={p.price_sensitivity:.1f}, "
                f"social_proof={p.social_proof:.1f}, "
                f"novelty_seeking={p.novelty_seeking:.1f}"
            )

        beliefs = "\n".join(f"- {b}" for b in agent.beliefs[:5]) or "Still forming opinions."

        system = RESEARCH_SUMMARIZE_SYSTEM.format(
            name=agent.name,
            age=agent.age,
            role=agent.role,
            honesty=p.honesty,
            ambition=p.ambition,
            empathy=p.empathy,
            conformity=p.conformity,
            market_personality=market_personality,
            beliefs=beliefs,
            query=query,
            reason=reason,
            search_results=search_results_text,
        )

        try:
            digest = await self.llm.generate(
                system=system,
                user="What did you learn? Summarize in 2-3 sentences.",
                json_mode=False,
                max_tokens=200,
            )
            return digest.strip()
        except Exception as e:
            logger.warning("Research summarization failed for agent %s: %s", agent.name, e)
            return ""
