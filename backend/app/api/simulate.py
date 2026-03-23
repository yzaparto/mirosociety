from __future__ import annotations
import asyncio
import json
import uuid
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from app.models.simulation import SSEEvent, SimulationStatus, SpeedMode, ForkRequest
from app.models.world import WorldState, WorldMetrics
from app.models.demographics import DemographicProfile
from app.services.census import CensusService

from enum import Enum

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _serialize_event_data(data: dict) -> str:
    def _default(obj):
        if isinstance(obj, Enum):
            return obj.value
        return str(obj)
    return json.dumps(data, default=_default)


class SegmentInput(BaseModel):
    name: str
    description: str
    count: int | None = None


class SimulateRequest(BaseModel):
    rules: str
    population: int = 25
    duration_days: int = 365
    proposed_change: str | None = None
    segments: list[SegmentInput] | None = None
    city: str | None = None

    @field_validator("rules")
    @classmethod
    def rules_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Rules cannot be empty")
        return v.strip()

    @field_validator("population")
    @classmethod
    def population_range(cls, v):
        if v < 2 or v > 50:
            raise ValueError("Population must be between 2 and 50")
        return v

    @field_validator("duration_days")
    @classmethod
    def duration_range(cls, v):
        if v < 1 or v > 365:
            raise ValueError("Duration must be between 1 and 365 days")
        return v


class InjectRequest(BaseModel):
    event: str


class SpeedRequest(BaseModel):
    mode: str


@router.post("/simulate")
async def simulate(req: SimulateRequest, request: Request):
    sim_id = str(uuid.uuid4())[:12]
    store = request.app.state.store
    world_gen = request.app.state.world_generator
    citizen_gen = request.app.state.citizen_generator
    engine = request.app.state.engine

    await store.create(sim_id, req.rules)

    cancelled = request.app.state.cancelled_sims

    async def run_pipeline():
        event_queue = request.app.state.event_queues.get(sim_id)
        if not event_queue:
            return

        try:
            await event_queue.put(SSEEvent(type="status", data={"status": "generating_world"}))
            await store.update_status(sim_id, SimulationStatus.GENERATING_WORLD.value)

            blueprint = await world_gen.generate(
                req.rules, req.population, req.duration_days,
                proposed_change=req.proposed_change,
            )

            if sim_id in cancelled:
                await event_queue.put(SSEEvent(type="cancelled", data={"message": "Simulation cancelled"}))
                return

            await store.set_meta(sim_id, "blueprint", blueprint.model_dump())
            if req.proposed_change:
                await store.set_meta(sim_id, "proposed_change", req.proposed_change)
            await store.update_status(sim_id, SimulationStatus.GENERATING_WORLD.value, world_name=blueprint.name)
            await event_queue.put(SSEEvent(type="world_ready", data=blueprint.model_dump()))

            if sim_id in cancelled:
                await event_queue.put(SSEEvent(type="cancelled", data={"message": "Simulation cancelled"}))
                return

            demographics: DemographicProfile | None = None
            if req.city:
                try:
                    census = CensusService(request.app.state.llm)
                    if "," in req.city:
                        city_name, state = [p.strip() for p in req.city.split(",", 1)]
                    else:
                        city_name, state = req.city.strip(), None
                    demographics = await census.get_profile(city_name, state)
                    await event_queue.put(SSEEvent(type="demographics_loaded", data={
                        "city": demographics.city_name,
                        "state": demographics.state,
                        "population": demographics.population,
                        "median_income": demographics.median_household_income,
                        "poverty_rate": demographics.poverty_rate,
                    }))
                except Exception as e:
                    logger.warning("Demographics fetch failed for %s: %s", req.city, e)

            await event_queue.put(SSEEvent(type="status", data={"status": "generating_citizens"}))
            await store.update_status(sim_id, SimulationStatus.GENERATING_CITIZENS.value)

            async def on_citizen(agent):
                if sim_id in cancelled:
                    raise asyncio.CancelledError()
                await store.save_agent(sim_id, agent)
                await event_queue.put(SSEEvent(type="citizen_generated", data=agent.model_dump()))

            segments_dicts = [s.model_dump() for s in req.segments] if req.segments else None
            agents = await citizen_gen.generate_fast(
                blueprint, req.population, on_citizen=on_citizen,
                proposed_change=req.proposed_change,
                segments=segments_dicts,
                demographics=demographics,
            )

            for agent in agents:
                await store.save_agent(sim_id, agent)
                await event_queue.put(SSEEvent(type="citizen_generated", data=agent.model_dump()))

            if sim_id in cancelled:
                await event_queue.put(SSEEvent(type="cancelled", data={"message": "Simulation cancelled"}))
                return

            async def enrich_in_background():
                try:
                    enriched = await citizen_gen.enrich_background(blueprint, agents)
                    engine.deliver_enriched_agents(sim_id, enriched)
                    for agent in enriched:
                        await store.save_agent(sim_id, agent)
                    logger.info("Background enrichment complete for %s", sim_id)
                except Exception as e:
                    logger.warning("Background enrichment failed for %s: %s", sim_id, e)

            asyncio.create_task(enrich_in_background())

            world_state = WorldState(
                blueprint=blueprint,
                metrics=WorldMetrics(),
                community_rules=[],
            )

            await store.update_status(sim_id, SimulationStatus.RUNNING.value)

            async def emit(event: SSEEvent):
                await event_queue.put(event)

            await engine.run(sim_id, world_state, agents, emit)

        except asyncio.CancelledError:
            logger.info("Pipeline cancelled for %s", sim_id)
            await event_queue.put(SSEEvent(type="cancelled", data={"message": "Simulation cancelled"}))
        except Exception as e:
            logger.error("Pipeline failed for %s: %s", sim_id, e, exc_info=True)
            await event_queue.put(SSEEvent(type="error", data={"message": str(e)}))
        finally:
            cancelled.discard(sim_id)

    request.app.state.event_queues[sim_id] = asyncio.Queue()
    asyncio.create_task(run_pipeline())

    return {"simulation_id": sim_id}


@router.get("/simulation/{sim_id}/stream")
async def stream(sim_id: str, request: Request):
    queue = request.app.state.event_queues.get(sim_id)
    if not queue:
        raise HTTPException(404, "Simulation not found")

    async def event_generator() -> AsyncGenerator:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {"event": event.type, "data": _serialize_event_data(event.data)}
                    if event.type in ("simulation_complete", "error", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "keepalive", "data": "{}"}
        finally:
            request.app.state.event_queues.pop(sim_id, None)

    return EventSourceResponse(event_generator())


@router.get("/simulation/{sim_id}/state")
async def get_state(sim_id: str, request: Request):
    store = request.app.state.store
    sim = await store.get_simulation(sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")

    world_state = await store.get_world_state(sim_id)
    agents = await store.get_all_agents(sim_id)

    return {
        "simulation": sim,
        "world_state": world_state.model_dump() if world_state else None,
        "agent_count": len(agents),
    }


@router.post("/simulation/{sim_id}/inject")
async def inject(sim_id: str, req: InjectRequest, request: Request):
    engine = request.app.state.engine
    store = request.app.state.store

    world_state = await store.get_world_state(sim_id)
    agents = await store.get_all_agents(sim_id)

    if not world_state:
        raise HTTPException(404, "No world state")

    desc = await engine.inject_event(sim_id, req.event, world_state, agents)
    return {"description": desc}


@router.post("/simulation/{sim_id}/speed")
async def set_speed(sim_id: str, req: SpeedRequest, request: Request):
    engine = request.app.state.engine
    try:
        mode = SpeedMode(req.mode)
    except ValueError:
        raise HTTPException(400, f"Invalid speed mode: {req.mode}")
    await engine.set_speed(sim_id, mode)
    return {"mode": mode.value}


@router.post("/simulation/{sim_id}/pause")
async def pause(sim_id: str, request: Request):
    found = await request.app.state.engine.pause(sim_id)
    if not found:
        raise HTTPException(404, "Simulation not running")
    return {"status": "paused"}


@router.post("/simulation/{sim_id}/resume")
async def resume(sim_id: str, request: Request):
    found = await request.app.state.engine.resume(sim_id)
    if not found:
        raise HTTPException(404, "Simulation not running")
    return {"status": "resumed"}


@router.post("/simulation/{sim_id}/stop")
async def stop(sim_id: str, request: Request):
    found = await request.app.state.engine.stop(sim_id)
    if not found:
        raise HTTPException(404, "Simulation not running")
    return {"status": "stopped"}


@router.post("/simulation/{sim_id}/cancel")
async def cancel(sim_id: str, request: Request):
    engine = request.app.state.engine
    cancelled = request.app.state.cancelled_sims

    stopped = await engine.stop(sim_id)
    if stopped:
        return {"status": "stopped"}

    cancelled.add(sim_id)
    return {"status": "cancelled"}


@router.get("/simulation/{sim_id}/report")
async def get_report(sim_id: str, request: Request):
    store = request.app.state.store
    result = await store.get_report(sim_id)
    if result.get("status") == "ready":
        return result["report"]
    return result


@router.post("/simulation/{sim_id}/publish")
async def publish(sim_id: str, request: Request):
    await request.app.state.store.publish(sim_id)
    return {"published": True}


@router.get("/simulation/{sim_id}/compare/{fork_id}")
async def compare(sim_id: str, fork_id: str, request: Request):
    store = request.app.state.store
    narrator = request.app.state.narrator

    source_state = await store.get_world_state(sim_id)
    fork_state = await store.get_world_state(fork_id)

    if not source_state or not fork_state:
        raise HTTPException(404, "Simulation not found")

    source_metrics = await store.get_metrics_history(sim_id)
    fork_metrics = await store.get_metrics_history(fork_id)

    source_agents = await store.get_all_agents(sim_id)
    fork_agents = await store.get_all_agents(fork_id)

    async def _get_or_generate_report(sid):
        cached = await store.get_report(sid)
        if cached and cached.get("status") == "ready":
            return cached["report"]
        rpt = await narrator.generate_report(sid, store)
        if "error" not in rpt:
            await store.save_report(sid, rpt)
        return rpt

    source_report = await _get_or_generate_report(sim_id)
    fork_report = await _get_or_generate_report(fork_id)

    return {
        "source": {
            "id": sim_id,
            "report": source_report,
            "metrics_history": source_metrics,
            "final_day": source_state.day,
        },
        "fork": {
            "id": fork_id,
            "report": fork_report,
            "metrics_history": fork_metrics,
            "final_day": fork_state.day,
        },
    }


@router.get("/simulation/{sim_id}/forecast")
async def get_forecast(
    sim_id: str,
    request: Request,
    horizon: int = Query(default=30, ge=1, le=365),
):
    store = request.app.state.store
    forecast = getattr(request.app.state, "forecast", None)

    if not forecast or not forecast.available:
        return {"error": "Forecast service not available"}

    metrics_history = await store.get_metrics_history(sim_id)
    if not metrics_history:
        raise HTTPException(404, "No metrics data found")

    analysis = forecast.analyze(metrics_history, horizon=horizon)
    causal_links = forecast.discover_causality(sim_id)
    counterfactuals = forecast.compute_counterfactuals(sim_id)

    return {
        "analysis": analysis,
        "causal_links": [
            {"cause": l.cause, "effect": l.effect, "lag": l.lag,
             "p_value": l.p_value, "strength": l.strength}
            for l in causal_links
        ],
        "counterfactuals": [
            {"event_round": c.event_round, "event_description": c.event_description,
             "metric_impacts": c.metric_impacts}
            for c in counterfactuals
        ],
    }


@router.post("/simulation/{sim_id}/fork")
async def fork(sim_id: str, req: ForkRequest, request: Request):
    store = request.app.state.store
    engine = request.app.state.engine

    source = await store.get_simulation(sim_id)
    if not source:
        raise HTTPException(404, "Source simulation not found")

    fork_id = str(uuid.uuid4())[:12]
    source_world = await store.get_world_state(sim_id)
    rounds_per_day = source_world.blueprint.time_config.rounds_per_day if source_world else 3
    fork_round = req.fork_at_day * rounds_per_day

    await store.create(fork_id, source.get("rules_text", ""))
    await store.update_status(fork_id, SimulationStatus.PAUSED.value,
                             forked_from=sim_id,
                             world_name=source.get("world_name", ""),
                             agent_count=source.get("agent_count", 0))
    await store.copy_state_at_round(sim_id, fork_id, fork_round)
    await store.increment_fork_count(sim_id)

    if req.changes:
        world_state = await store.get_world_state(fork_id)
        agents = await store.get_all_agents(fork_id)
        if world_state and agents:
            await engine.inject_event(fork_id, req.changes, world_state, agents)

    event_queue = asyncio.Queue()
    request.app.state.event_queues[fork_id] = event_queue

    async def run_fork():
        try:
            world_state = await store.get_world_state(fork_id)
            agents = await store.get_all_agents(fork_id)
            if not world_state or not agents:
                await event_queue.put(SSEEvent(type="error", data={"message": "Fork state not found"}))
                return

            await event_queue.put(SSEEvent(
                type="status", data={"status": "forked_simulation"}
            ))

            await event_queue.put(SSEEvent(
                type="world_ready", data=world_state.blueprint.model_dump()
            ))

            for agent in agents:
                await event_queue.put(SSEEvent(
                    type="citizen_generated", data=agent.model_dump()
                ))

            await store.update_status(
                fork_id, SimulationStatus.RUNNING.value,
                world_name=world_state.blueprint.name,
                agent_count=len(agents),
            )

            async def emit(event: SSEEvent):
                await event_queue.put(event)

            await engine.run(fork_id, world_state, agents, emit, start_round=fork_round)

        except Exception as e:
            logger.error("Fork pipeline failed for %s: %s", fork_id, e, exc_info=True)
            await event_queue.put(SSEEvent(type="error", data={"message": str(e)}))

    asyncio.create_task(run_fork())

    return {"simulation_id": fork_id, "forked_from": sim_id, "fork_at_day": req.fork_at_day}
