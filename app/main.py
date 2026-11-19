from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.openrouter import chat_completion, list_free_models
from app.retriever import Retriever

app = FastAPI(title="DarGlobal & Wasalt Public Information Assistant")
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
retriever = Retriever()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    model: str | None = Field(default=None, max_length=200)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "documents": len(retriever.records)}


@app.get("/api/models")
async def models():
    return {"models": await list_free_models()}


def is_knowledge_scope_question(message: str) -> bool:
    text = message.lower()
    return any(phrase in text for phrase in (
        "how many", "how much information", "how many information",
        "what sources", "how many sources", "which sources",
        "what data", "knowledge base", "database", "scraped",
        "information do you have", "real estate information",
    ))


def classify_intent(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ("difference", "compare", "versus", " vs ")):
        return "comparison"
    if any(word in text for word in ("price", "cost", "how much")):
        return "pricing"
    if any(word in text for word in ("available", "availability", "for sale", "for rent")):
        return "availability"
    if any(word in text for word in ("where", "location", "country", "city", "operate")):
        return "location"
    return "information"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if is_knowledge_scope_question(request.message):
        source_counts = {}
        for record in retriever.records:
            source = record.get("source", "Unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        source_summary = ", ".join(
            f"{source}: {count} {'page' if count == 1 else 'pages'}"
            for source, count in source_counts.items()
        )
        answer = (
            f"I currently have {len(retriever.records)} indexed public pages from 2 sources — {source_summary}. "
            "That is the amount of real-estate information loaded into this chatbot's knowledge base."
        )
        return {
            "answer": answer,
            "sources": [],
            "intent": "knowledge_scope",
            "confidence": "high",
            "retrieval_score": 1.0,
            "model": "knowledge-base metadata",
            "stages": [{"label": "Checked knowledge-base metadata", "detail": f"{len(retriever.records)} indexed pages across {len(source_counts)} sources", "status": "complete"}],
        }

    resolved_message = retriever.resolve_context(request.message, request.history)
    context = retriever.search(resolved_message)
    intent = classify_intent(request.message)
    best_score = context[0]["score"] if context else 0.0
    confidence = "high" if best_score >= 0.45 else "medium" if best_score >= 0.20 else "low"
    messages = [*request.history, {"role": "user", "content": resolved_message}]

    selected_model = request.model
    if selected_model and selected_model != "openrouter/free":
        available = await list_free_models()
        if not any(model["id"] == selected_model for model in available):
            selected_model = None

    answer = await chat_completion(messages, context, selected_model)
    sources = [
        {"title": item["title"], "url": item["url"], "source": item["source"]}
        for item in context
    ]
    evidence_names = list(dict.fromkeys(item["source"] for item in context))
    stages = [
        {"label": "Understood the question", "detail": f"Intent identified as {intent}", "status": "complete"},
        {"label": "Searched the knowledge base", "detail": f"{len(context)} relevant evidence chunks found", "status": "complete"},
        {"label": "Cross-checked sources", "detail": ", ".join(evidence_names) if evidence_names else "No supported evidence found", "status": "complete" if evidence_names else "warning"},
        {"label": "Prepared a grounded answer", "detail": f"Retrieval confidence: {confidence}", "status": "complete"},
    ]
    return {
        "answer": answer,
        "sources": sources,
        "intent": intent,
        "confidence": confidence,
        "retrieval_score": round(best_score, 3),
        "model": selected_model or os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        "stages": stages,
    }
