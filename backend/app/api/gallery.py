from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api")


@router.get("/gallery")
async def list_gallery(request: Request, sort: str = "recent"):
    sims = await request.app.state.store.list_simulations(public_only=True, sort=sort)
    return {"simulations": sims}


@router.get("/gallery/{sim_id}")
async def get_gallery_item(sim_id: str, request: Request):
    store = request.app.state.store
    sim = await store.get_simulation(sim_id)
    if not sim or not sim.get("is_public"):
        raise HTTPException(404, "Simulation not found in gallery")
    await store.increment_view_count(sim_id)
    cached = await store.get_report(sim_id)
    if cached and cached.get("status") == "ready":
        return cached["report"]
    narrator = request.app.state.narrator
    report = await narrator.generate_report(sim_id, store)
    return report
