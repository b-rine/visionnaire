from contextlib import asynccontextmanager

from app.logging_utils import configure_logging
from app.routers import photos
from app.services.vector_store import init_collection
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_collection()
    yield


app = FastAPI(title="Visionnaire", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photos.router, prefix="/api")
