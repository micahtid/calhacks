from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import close_client, get_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_client()


app = FastAPI(title="Agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await get_client().admin.command("ping")
        db = "ok"
    except Exception as e:
        db = f"error: {e.__class__.__name__}"
    return {"status": "ok", "db": db}
