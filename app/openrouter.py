import os
from typing import Any

import httpx


async def list_free_models() -> list[dict[str, str]]:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return []

    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
        response.raise_for_status()
        models = response.json().get("data", [])

    free_models = []
    for model in models:
        pricing = model.get("pricing") or {}
        is_free = (
            model.get("id", "").endswith(":free")
            or (
                str(pricing.get("prompt", "0")) == "0"
                and str(pricing.get("completion", "0")) == "0"
            )
        )
        if is_free:
            free_models.append({"id": model["id"], "name": model.get("name", model["id"])})
    return free_models


async def chat_completion(messages: list[dict[str, str]], context: list[dict[str, Any]], model: str | None = None) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return "The assistant is not configured yet. An administrator needs to set OPENROUTER_API_KEY."

    system = (
        "You are a concise property-information assistant for DarGlobal and Wasalt. "
        "Answer only the question asked. Give the shortest useful answer in natural human language. "
        "Do not add unrelated company history, lists, investment advice, prices, availability, or follow-up suggestions unless requested. "
        "Use no more than 2 short paragraphs or 3 short bullets. "
        "Use only the supplied context. Never infer current prices or availability. "
        "For a comparison, give only the key difference in purpose or role. "
        "Include source URLs inline only for claims that come from the supplied context. "
        "If the context does not support the answer, respond with one short sentence explaining that the requested information is not available in the source data."
    )
    if context:
        context_text = "\n\n".join(
            f"Source: {item['title']} ({item['source']})\nURL: {item['url']}\nContent: {item['text']}"
            for item in context
        )
        system += f"\n\nCONTEXT:\n{context_text}"

    payload = {
        "model": model or os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        "messages": [{"role": "system", "content": system}, *messages[-8:]],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "DarGlobal Wasalt Assistant"),
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]
