from contextlib import asynccontextmanager

from app.routers import caption, photos
from app.services.vector_store import init_collection
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

app.include_router(caption.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
