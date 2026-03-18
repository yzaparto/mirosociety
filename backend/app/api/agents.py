from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.services.llm import LLMClient

router = APIRouter(prefix="/api")


class InterviewRequest(BaseModel):
    question: str


@router.get("/simulation/{sim_id}/agents")
async def list_agents(sim_id: str, request: Request):
    agents = await request.app.state.store.get_all_agents(sim_id)
    return {"agents": [a.model_dump() for a in agents]}


@router.get("/simulation/{sim_id}/agent/{agent_id}")
async def get_agent(sim_id: str, agent_id: int, request: Request):
    agent = await request.app.state.store.get_agent(sim_id, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.model_dump()


@router.post("/simulation/{sim_id}/agent/{agent_id}/interview")
async def interview(sim_id: str, agent_id: int, req: InterviewRequest, request: Request):
    store = request.app.state.store
    llm: LLMClient = request.app.state.llm

    agent = await store.get_agent(sim_id, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    world_state = await store.get_world_state(sim_id)
    world_name = world_state.blueprint.name if world_state else "the settlement"

    system = (
        f"You are {agent.name}, a {agent.age}-year-old {agent.role} in {world_name}.\n"
        f"Your personality: honesty={agent.personality.honesty:.1f}, "
        f"empathy={agent.personality.empathy:.1f}, "
        f"confrontational={agent.personality.confrontational:.1f}\n"
        f"Your core memories: {'; '.join(agent.core_memory[:5])}\n"
        f"Your beliefs: {'; '.join(agent.beliefs[:5])}\n"
        f"Your emotional state: {agent.emotional_state}\n\n"
        "Someone approaches and asks you a question. Respond in character. "
        "Be authentic to your personality. Reference specific events from your memory. "
        "Keep it to 2-3 sentences."
    )

    response = await llm.generate(system=system, user=req.question, max_tokens=200)
    return {"response": response, "emotional_state": agent.emotional_state}
