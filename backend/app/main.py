from __future__ import annotations
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.db.store import SimulationStore
from app.services.llm import LLMClient
from app.services.world_generator import WorldGenerator
from app.services.citizen_generator import CitizenGenerator
from app.services.tension import TensionEngine
from app.services.resolver import ActionResolver
from app.services.narrator import Narrator
from app.services.engine import SimulationEngine
from app.api.simulate import router as simulate_router
from app.api.agents import router as agents_router
from app.api.gallery import router as gallery_router
from app.api.presets import router as presets_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SimulationStore(settings.database_dir)
    await store.init()

    llm = LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_concurrent=settings.max_concurrent_llm_calls,
    )

    world_gen = WorldGenerator(llm)
    citizen_gen = CitizenGenerator(llm)
    tension = TensionEngine(llm)
    resolver = ActionResolver()
    narrator = Narrator(llm)
    engine = SimulationEngine(llm, store, tension, resolver, narrator)

    app.state.store = store
    app.state.llm = llm
    app.state.world_generator = world_gen
    app.state.citizen_generator = citizen_gen
    app.state.engine = engine
    app.state.narrator = narrator
    app.state.event_queues = {}

    logger.info("MiroSociety started — LLM: %s @ %s", settings.llm_model, settings.llm_base_url)
    yield
    logger.info("MiroSociety shutting down")


app = FastAPI(title="MiroSociety", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulate_router)
app.include_router(agents_router)
app.include_router(gallery_router)
app.include_router(presets_router)


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.llm_model}


static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = (static_dir / path).resolve()
        if file_path.is_relative_to(static_dir.resolve()) and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")
