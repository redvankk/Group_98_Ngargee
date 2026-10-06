"""FastAPI app for the RMIT Clubs Assistant.

Run from the backend folder:  uvicorn main:app --reload --port 8000
"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from rag import service
from rag.config import settings
from rag.generator import ollama_status, warm_up
from rag.schemas import ChatRequest, ChatResponse

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("clubs-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.init()  # loads data and builds/loads the index once at startup
    llm = ollama_status()
    if settings.ollama_enabled and not llm["model_available"]:
        log.warning(
            "Ollama model %s is not available (reachable=%s). Answers will use the "
            "extractive fallback. Start Ollama and run: ollama pull %s",
            settings.ollama_model, llm["reachable"], settings.ollama_model,
        )
    else:
        # Load the model in the background so the first question is fast.
        threading.Thread(target=warm_up, daemon=True).start()
    yield


app = FastAPI(
    title="RMIT Clubs RAG API",
    version="2.0.0",
    description="Club discovery assistant: retrieval over RMIT club data + a local Ollama LLM.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root():
    return {"message": "RMIT Clubs RAG API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    retriever = service.get_retriever()
    llm = ollama_status()
    llm_ready = llm["enabled"] and llm["model_available"]
    return {
        "status": "ok",
        # Short label shown in the website header, e.g. "RAG · llama3.2:3b online"
        "mode": f"RAG · {settings.ollama_model}" if llm_ready else "Retrieval only",
        "retriever": retriever.name,
        "clubs_loaded": len({c["club_id"] for c in retriever.chunks}),
        "chunks_loaded": len(retriever.chunks),
        "embedding_model": settings.embedding_model if retriever.name != "bm25" else None,
        "llm": llm,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    history = [m.model_dump() for m in payload.history]
    try:
        return service.answer_question(payload.question, history, payload.top_k)
    except Exception as exc:
        log.exception("Chat request failed")
        raise HTTPException(status_code=500, detail="The assistant hit an internal error.") from exc


@app.get("/clubs/search")
def search_clubs(
    q: str = Query(min_length=1, max_length=300),
    limit: int = Query(default=6, ge=1, le=10),
):
    results = service.get_retriever().search(q, top_k=limit)
    return {
        "results": [
            {
                "id": r["club_id"],
                "name": r["name"],
                "category": r["category"],
                "url": r["url"],
                "score": round(r["score"], 4),
            }
            for r in results
            if r["score"] > 0  # BM25 gives 0 when no query word matches
        ]
    }


@app.post("/admin/reindex")
def reindex():
    if not settings.allow_reindex:
        raise HTTPException(status_code=403, detail="Reindexing is disabled. Set ALLOW_REINDEX=true in .env.")
    retriever = service.init(rebuild=True)
    return {"status": "rebuilt", "retriever": retriever.name, "chunks": len(retriever.chunks)}
