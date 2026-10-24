import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

# Local dev only: hosted deploys set MONGODB_URI in the platform and ship no env files.
# Earlier files win (load_dotenv doesn't override): agent-local first, then repo root.
_AGENT = Path(__file__).resolve().parents[1]
for _env in (_AGENT / ".env.local", _AGENT / ".env", _AGENT.parent.parent / ".env.local", _AGENT.parent.parent / ".env"):
    load_dotenv(_env)

_client: AsyncMongoClient | None = None


def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI is not set; copy .env.example to .env")
        _client = AsyncMongoClient(uri, appname="calhacks-agent")
    return _client


def get_db() -> AsyncDatabase:
    return get_client()[os.environ.get("MONGODB_DB_AGENT", "agent")]


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
