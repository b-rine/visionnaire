import asyncio

from app.services.triton_client import triton_ready
from app.services.vector_store import qdrant_ready
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    checks = await asyncio.gather(
        qdrant_ready(),
        triton_ready(),
        return_exceptions=True,
    )
    components = {
        "qdrant": checks[0] is True,
        "triton": checks[1] is True,
    }
    ready = all(components.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "unavailable",
            "components": components,
        },
    )
