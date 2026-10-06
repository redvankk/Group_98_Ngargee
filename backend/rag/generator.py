"""Answer generation with a local Ollama model (default: llama3.2:3b).

The model only sees the retrieved chunks, numbered [1], [2], ... It is asked
to cite them by number, and the API returns the same numbered sources so the
frontend can show which club each citation refers to.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date

from .config import settings

log = logging.getLogger(__name__)

# Response modes (returned to the frontend and logged for evaluation)
MODE_RAG = "rag"                    # LLM answer grounded in retrieved sources
MODE_NO_MATCH = "no-match"          # nothing relevant retrieved; assistant declines
MODE_RETRIEVAL_ONLY = "retrieval-only"  # Ollama disabled in config
MODE_LLM_ERROR = "llm-error"        # Ollama failed; extractive fallback used

NO_MATCH_ANSWER = (
    "I couldn't find information about that in the RMIT club knowledge base, "
    "so I can't answer it reliably. Try rephrasing, or check the official "
    "RUSU club directory."
)

SYSTEM_PROMPT = """You are the RMIT Clubs Assistant. You help RMIT students find clubs \
and communities that match their interests, and explain how to get involved.

What you know: each numbered club record has the club's name, category, description,
campus, who can join, contact details and links where available. Some clubs also list
an event, with the date the listing was checked. Today is {today}. Only call an event
upcoming if its date is after today; otherwise say when it was listed for. Never
suggest events for clubs that list none.

Rules:
1. Use ONLY the numbered club records. Do not use outside knowledge.
2. Cite the records you use with their number in square brackets, e.g. [1] or [2][3].
3. Never invent club names, events, dates, contacts, links or membership rules.
4. Answer as much as the records allow. If some of what was asked isn't in them,
   say briefly what is missing, e.g. "I don't have details on what CSIT does yet,
   but you can contact them at ... [1]".
5. When a club's description is only a generic greeting, say its details are
   limited and point to its contact details or page instead of guessing.
6. When the student wants a recommendation, suggest two or three suitable clubs if
   the records support it, each with one line on why it fits.
7. To compare clubs, describe each one's focus and how to join, then the main difference.
8. Start with the answer itself. Don't refer to "the sources", "the records",
   "the information provided" or "the context"; the citation numbers are enough.
9. Don't assume the student's nationality, culture, religion or politics. Only recommend
   a club for a particular culture, faith or political view if the student mentions that
   background or topic. For general questions about meeting people, recommend clubs
   that anyone can join.
10. If the request is broad (e.g. making friends, getting involved), recommend two or
   three open clubs, then end with one short question about what they're into.
11. Clubs marked "Type: Computing" are the complete list of the five computing clubs;
   use them for questions about the computing clubs as a group (e.g. how many there are).
12. Don't mention when a club joined Rubric or when its details were checked, unless asked.
13. When the student asks for a link, give the full URL exactly as it appears in the
   record, written plainly (no square brackets around it).
14. Be concise and friendly. If you can't help, say so in one sentence and suggest
   asking about a club's focus, how to join, or how to contact them."""

# Small models still sometimes open with this; strip it if they do.
_OPENER = re.compile(
    r"^(?:based on|according to|from) (?:the )?(?:provided |given |retrieved )?"
    r"(?:sources|records|club records|information|context)(?: provided| given| above)?[,:]?\s*",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d+)\]")


def clean_answer(answer: str) -> str:
    cleaned = _OPENER.sub("", answer.strip(), count=1)
    return cleaned[:1].upper() + cleaned[1:] if cleaned else answer


def cited_numbers(answer: str) -> set[int]:
    return {int(n) for n in _CITATION.findall(answer)}


@dataclass
class Generation:
    answer: str
    mode: str
    sources: list[dict]  # the numbered sources actually given to the model


def select_sources(results: list[dict], max_chars: int | None = None) -> list[dict]:
    """Relevant results that fit the context budget, in rank order."""
    budget = settings.max_context_chars if max_chars is None else max_chars
    selected, used = [], 0
    for item in results:
        if not item.get("relevant"):
            continue
        size = len(item["text"]) + 80
        if selected and used + size > budget:
            break
        selected.append(item)
        used += size
    return selected


def format_context(sources: list[dict]) -> str:
    blocks = []
    for number, item in enumerate(sources, 1):
        url = item.get("url", "")
        link = f"\nLink: {url}" if url and url not in item["text"] else ""
        blocks.append(f"[{number}]\n{item['text']}{link}")
    return "\n\n".join(blocks)


def build_messages(question: str, history: list[dict], sources: list[dict]) -> list[dict]:
    today = date.today().strftime("%d %B %Y")
    messages = [{"role": "system", "content": SYSTEM_PROMPT.replace("{today}", today)}]
    for turn in history[-settings.history_turns:]:
        role = "assistant" if turn["role"] in {"assistant", "bot"} else "user"
        messages.append({"role": role, "content": turn["content"]})
    messages.append(
        {
            "role": "user",
            "content": (
                f"Club records:\n\n{format_context(sources)}\n\n"
                f"Question: {question}\n\n"
                "Answer using only the club records above and cite them by number."
            ),
        }
    )
    return messages


def extractive_answer(sources: list[dict]) -> str:
    """Plain summary of the sources, used when the LLM is off or fails."""
    lines = ["Here are the most relevant clubs I found:"]
    for number, item in enumerate(sources[:3], 1):
        text = " ".join(item["text"].split())
        lines.append(f"• [{number}] {text[:300]}")
    lines.append("Check the linked sources for the latest details.")
    return "\n".join(lines)


def call_ollama(messages: list[dict]) -> str:
    from ollama import Client

    client = Client(host=settings.ollama_host, timeout=settings.ollama_timeout)
    response = client.chat(
        model=settings.ollama_model,
        messages=messages,
        options={
            "temperature": settings.ollama_temperature,
            "num_ctx": settings.ollama_num_ctx,
        },
        keep_alive=settings.ollama_keep_alive,
    )
    answer = (response.message.content or "").strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty response")
    return answer


def generate_answer(question: str, history: list[dict], results: list[dict]) -> Generation:
    sources = select_sources(results)
    if not sources:
        return Generation(NO_MATCH_ANSWER, MODE_NO_MATCH, [])

    if not settings.ollama_enabled:
        return Generation(extractive_answer(sources), MODE_RETRIEVAL_ONLY, sources)

    try:
        answer = clean_answer(call_ollama(build_messages(question, history, sources)))
        return Generation(answer, MODE_RAG, sources)
    except Exception:
        log.exception("Ollama generation failed; using extractive fallback")
        return Generation(extractive_answer(sources), MODE_LLM_ERROR, sources)


def warm_up() -> None:
    """Load the model into memory so the first real question isn't slow."""
    if not settings.ollama_enabled:
        return
    try:
        from ollama import Client

        # Same options as real requests: a different num_ctx would make Ollama
        # reload the model on the first question, undoing the warm-up.
        Client(host=settings.ollama_host, timeout=settings.ollama_timeout).generate(
            model=settings.ollama_model,
            prompt="Hi",
            options={"temperature": settings.ollama_temperature, "num_ctx": settings.ollama_num_ctx, "num_predict": 1},
            keep_alive=settings.ollama_keep_alive,
        )
        log.info("Ollama model %s loaded", settings.ollama_model)
    except Exception as exc:
        log.warning("Could not pre-load the Ollama model: %s", exc)


def ollama_status() -> dict:
    """Whether Ollama is reachable and the configured model is downloaded."""
    status = {"enabled": settings.ollama_enabled, "model": settings.ollama_model,
              "reachable": False, "model_available": False}
    if not settings.ollama_enabled:
        return status
    try:
        from ollama import Client

        models = Client(host=settings.ollama_host, timeout=3).list().models
        status["reachable"] = True
        names = {m.model for m in models}
        wanted = settings.ollama_model
        status["model_available"] = wanted in names or f"{wanted}:latest" in names
    except Exception as exc:  # Ollama not running
        status["error"] = type(exc).__name__
    return status
