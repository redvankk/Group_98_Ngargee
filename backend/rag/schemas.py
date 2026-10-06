from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant", "bot"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=4, ge=1, le=8)


class Link(BaseModel):
    label: str
    url: str


class Source(BaseModel):
    number: int
    id: str
    name: str
    url: str
    category: str
    score: float
    excerpt: str | None = None
    links: list[Link] = Field(default_factory=list)


class Timings(BaseModel):
    retrieval_ms: int
    generation_ms: int
    total_ms: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    mode: str
    retriever: str
    retrieval_query: str
    follow_ups: list[str] = Field(default_factory=list)
    citation_fixes: int = 0
    timings: Timings
