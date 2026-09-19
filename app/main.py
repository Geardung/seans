import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.jobs.reaper import reaper_loop
from app.routers.auth import router as auth_router
from app.routers.history import router as history_router
from app.routers.library import router as library_router
from app.routers.media import router as media_router
from app.routers.reviews import router as reviews_router
from app.routers.rooms import router as rooms_router
from app.routers.tasks import router as tasks_router
from app.routers.worker import router as worker_router
from app.routers.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    reaper_task = asyncio.create_task(reaper_loop())
    yield
    reaper_task.cancel()
    try:
        await reaper_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Seans API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(media_router)
app.include_router(tasks_router)
app.include_router(library_router)
app.include_router(worker_router)
app.include_router(rooms_router)
app.include_router(history_router)
app.include_router(reviews_router)
app.include_router(ws_router)

if os.getenv("ENV", "dev") == "dev":
    from app.routers.dev import router as dev_router

    app.include_router(dev_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
