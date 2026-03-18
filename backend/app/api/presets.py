from fastapi import APIRouter
from app.presets import PRESETS

router = APIRouter(prefix="/api")


@router.get("/presets")
async def get_presets():
    return {"presets": PRESETS}
