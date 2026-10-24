"""Bitdeer chat client (OpenAI-compatible): streams the model's reasoning, then returns its JSON answer.

JSON-object mode plus our own validation, not strict json_schema: redteam/src/redteam/bitdeer.py notes runaway
whitespace with schemas on Bitdeer.
"""

import json
import os
from collections.abc import AsyncIterator

import httpx

BASE = "https://api-inference.bitdeer.ai/v1"
DEFAULT_MODEL = "zai-org/GLM-5.3-Flash"
# GLM-5.3-Flash reasons before it answers, and the reasoning counts against max_tokens: at 600 it used them all
# and the answer came back empty.
MAX_TOKENS = 6000


class LLMError(RuntimeError):
    pass


def parse_json(text: str) -> dict:
    """The answer as a JSON object, tolerating a ```json fence or text around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise LLMError(f"no JSON object in the answer: {text[:200]!r}")
    try:
        return json.loads(text[start:end + 1])
    except ValueError as e:
        raise LLMError(f"answer is not valid JSON: {e}") from e


async def complete_json(client: httpx.AsyncClient, messages: list[dict]) -> AsyncIterator[tuple[str, object]]:
    """Yields ("reasoning", text) for each reasoning delta as it streams, then ("answer", dict) once."""
    key = os.environ.get("BITDEER_API_KEY")
    if not key:
        raise LLMError("BITDEER_API_KEY missing (apps/agent/api/.env locally, a service variable on Railway)")
    body = {"model": os.environ.get("BITDEER_MODEL", DEFAULT_MODEL), "messages": messages, "stream": True,
            "temperature": 0.2, "max_tokens": MAX_TOKENS, "response_format": {"type": "json_object"}}
    answer = []
    async with client.stream("POST", f"{BASE}/chat/completions", json=body,
                             headers={"Authorization": f"Bearer {key}"}) as res:
        if res.status_code != 200:
            raise LLMError(f"Bitdeer {res.status_code}: {(await res.aread())[:300]!r}")
        async for line in res.aiter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            choices = json.loads(line[6:]).get("choices") or []  # the last chunk carries only usage
            delta = (choices[0].get("delta") or {}) if choices else {}
            if text := delta.get("reasoning_content"):
                yield "reasoning", text
            if text := delta.get("content"):
                answer.append(text)
    yield "answer", parse_json("".join(answer))
