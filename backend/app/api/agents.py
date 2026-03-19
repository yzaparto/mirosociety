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

    if agent.life_state:
        life_lines = []

        # Domain levels
        for domain in ["finances", "career", "health"]:
            val = getattr(agent.life_state, domain, 0.5)
            if val < 0.3:
                life_lines.append(f"Your {domain} situation is dire")
            elif val < 0.5:
                life_lines.append(f"Your {domain} is tight but you manage")
            elif val > 0.7:
                life_lines.append(f"Your {domain} is in good shape")

        # Family
        if agent.life_state.family:
            family_strs = [f"{f.name} ({f.relation}, {f.age}, {f.status})" for f in agent.life_state.family]
            life_lines.append(f"Your family: {', '.join(family_strs)}")

        # Pressures
        if agent.life_state.pressures:
            pressure_strs = [p.description for p in agent.life_state.pressures[:3]]
            life_lines.append(f"What weighs on you: {'; '.join(pressure_strs)}")

        # Childhood
        if agent.life_state.childhood_summary:
            life_lines.append(f"Your upbringing: {agent.life_state.childhood_summary[:200]}")

        if life_lines:
            system += "\n\nYOUR LIFE SITUATION:\n" + "\n".join(life_lines)
            system += "\n\nWhen answering, let your life situation color your responses naturally. Reference family, pressures, or your past when relevant."

    response = await llm.generate(system=system, user=req.question, max_tokens=200)
    return {"response": response, "emotional_state": agent.emotional_state}
