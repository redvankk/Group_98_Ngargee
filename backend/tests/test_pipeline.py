"""Fast tests that need no embedding model and no Ollama."""
import numpy as np

from rag import generator, service
from rag.chunking import club_to_chunks
from rag.knowledge_base import load_chunks
from rag.retrievers import BM25Retriever, DenseRetriever, HybridRetriever
from rag.retrievers.base import top_per_club

CHUNKS = [
    {"chunk_id": "chess::0", "club_id": "chess", "name": "Chess Club", "category": "Games",
     "url": "https://example.org/chess", "chunk_type": "overview",
     "text": "Club: Chess Club\nCategory: Games\nDescription: Weekly chess nights and tournaments."},
    {"chunk_id": "chess::1", "club_id": "chess", "name": "Chess Club", "category": "Games",
     "url": "https://example.org/chess", "chunk_type": "membership_contact",
     "text": "Club: Chess Club\nClub email: chess@example.org"},
    {"chunk_id": "cyber::0", "club_id": "cyber", "name": "Cyber Club", "category": "Tech",
     "url": "", "chunk_type": "overview",
     "text": "Club: Cyber Club\nCategory: Tech\nDescription: Capture the flag and ethical hacking."},
]


class FakeDense(DenseRetriever):
    """Bag-of-words 'embedding' so dense/hybrid logic can be tested offline."""

    def build(self, chunks, rebuild=False):
        self.chunks = chunks
        self.vocab = sorted({w for c in chunks for w in c["text"].lower().split()})
        self.embeddings = np.stack([self._vec(c["text"]) for c in chunks])

    def _vec(self, text):
        words = text.lower().split()
        v = np.array([words.count(w) for w in self.vocab], dtype="float32")
        return v / (np.linalg.norm(v) or 1)

    def score(self, query):
        s = self.embeddings @ self._vec(query)
        return s, s >= self.min_score


def test_real_data_loads():
    chunks = load_chunks()
    assert len({c["club_id"] for c in chunks}) > 90
    assert all(c["text"].startswith("Club: ") for c in chunks)


def test_chunking_skips_empty_contact_chunk():
    chunks = club_to_chunks({"id": "x", "name": "X", "category": "Games", "description": "d"})
    assert [c["chunk_type"] for c in chunks] == ["overview"]


def test_bm25_ranks_matching_club_first_and_ignores_labels():
    bm25 = BM25Retriever(min_score=0.5)
    bm25.build(CHUNKS)
    results = bm25.search("ethical hacking competitions", top_k=2)
    assert results[0]["club_id"] == "cyber" and results[0]["relevant"]
    # "category" is a label on every chunk, so it must not match anything
    scores, _ = bm25.score("category")
    assert scores.max() == 0


def test_one_result_per_club():
    scores = np.array([0.9, 0.8, 0.1])
    results = top_per_club(CHUNKS, scores, scores > 0.5, top_k=3)
    assert [r["club_id"] for r in results] == ["chess", "cyber"]
    assert results[1]["relevant"] is False


def test_hybrid_combines_both():
    dense, bm25 = FakeDense(min_score=0.3), BM25Retriever(min_score=0.5)
    hybrid = HybridRetriever(dense=dense, bm25=bm25)
    hybrid.build(CHUNKS)
    assert hybrid.search("chess tournaments", top_k=1)[0]["club_id"] == "chess"


def test_generator_declines_without_relevant_sources(monkeypatch):
    results = [{**CHUNKS[0], "score": 0.1, "relevant": False}]
    gen = generator.generate_answer("capital of France?", [], results)
    assert gen.mode == generator.MODE_NO_MATCH and gen.sources == []


def test_generator_falls_back_when_llm_fails(monkeypatch):
    def boom(messages):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(generator, "call_ollama", boom)
    results = [{**CHUNKS[0], "score": 0.9, "relevant": True}]
    gen = generator.generate_answer("chess?", [], results)
    assert gen.mode == generator.MODE_LLM_ERROR  # OLLAMA_ENABLED defaults to true
    assert "[1]" in gen.answer


def test_prompt_numbers_sources_and_keeps_recent_history():
    sources = [{**CHUNKS[0], "relevant": True}, {**CHUNKS[2], "relevant": True}]
    history = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    messages = generator.build_messages("which club?", history, sources)
    assert messages[0]["role"] == "system"
    assert len(messages) == 1 + generator.settings.history_turns + 1
    assert "[1]" in messages[-1]["content"] and "[2]" in messages[-1]["content"]
    assert "Club records" in messages[-1]["content"]
    assert "Link: https://example.org/chess" in messages[-1]["content"]


def test_service_end_to_end_without_llm(monkeypatch):
    bm25 = BM25Retriever(min_score=0.5)
    bm25.build(CHUNKS)
    monkeypatch.setattr(service, "_retriever", bm25)
    monkeypatch.setattr(generator, "call_ollama", lambda messages: "Try the Chess Club [1].")
    out = service.answer_question("chess nights", [], top_k=2)
    assert out["sources"][0]["number"] == 1 and out["sources"][0]["id"] == "chess"
    assert set(out["timings"]) == {"retrieval_ms", "generation_ms", "total_ms"}


def test_rewrite_query_adds_previous_question_to_short_follow_ups():
    history = [{"role": "user", "content": "any chess clubs?"}]
    assert "chess" in service.rewrite_query("how do I join?", history)


def test_new_topic_is_not_mixed_with_previous_question():
    history = [{"role": "user", "content": "I'm into cybersecurity and CTFs"}]
    assert service.rewrite_query("I'm new to Melbourne and want to make friends.", history) == (
        "I'm new to Melbourne and want to make friends."
    )
    assert "cybersecurity" in service.rewrite_query("How do I contact them?", history)


def test_only_cited_sources_are_returned(monkeypatch):
    bm25 = BM25Retriever(min_score=0.01)
    bm25.build(CHUNKS)
    monkeypatch.setattr(service, "_retriever", bm25)
    monkeypatch.setattr(generator, "call_ollama", lambda m: "Based on the sources provided, try [2].")
    out = service.answer_question("club chess hacking", [], top_k=2)
    assert [s["number"] for s in out["sources"]] == [2]
    assert out["answer"].startswith("Try [2]")
    assert out["follow_ups"] and all(out["sources"][0]["name"] in q for q in out["follow_ups"])


def test_follow_ups():
    from rag.followups import GENERAL, suggest_follow_ups

    two = [{"name": "Chess Club"}, {"name": "Cyber Club"}]
    assert suggest_follow_ups("any chess clubs?", two)[0] == "What's the difference between Chess Club and Cyber Club?"
    assert not any("join" in q for q in suggest_follow_ups("how do I join?", two))
    assert suggest_follow_ups("capital of France?", []) == GENERAL[:3]


def test_named_clubs_are_always_included(monkeypatch):
    bm25 = BM25Retriever(min_score=0.5)
    bm25.build(CHUNKS)
    monkeypatch.setattr(service, "_retriever", bm25)
    monkeypatch.setattr(service, "_matcher", service.ClubNameMatcher(CHUNKS))
    monkeypatch.setattr(service, "_club_records", service.build_club_records(CHUNKS))
    clubs = service.gather_clubs("compare Chess Club and Cyber Club", top_k=1)
    assert [c["club_id"] for c in clubs] == ["chess", "cyber"]
    # the whole club record is used, so contact details come along
    assert "chess@example.org" in clubs[0]["text"]


def test_answer_without_citations_shows_no_sources(monkeypatch):
    bm25 = BM25Retriever(min_score=0.01)
    bm25.build(CHUNKS)
    monkeypatch.setattr(service, "_retriever", bm25)
    monkeypatch.setattr(service, "_matcher", service.ClubNameMatcher(CHUNKS))
    monkeypatch.setattr(service, "_club_records", service.build_club_records(CHUNKS))
    monkeypatch.setattr(generator, "call_ollama", lambda m: "I don't have event dates.")
    out = service.answer_question("club events coming up", [])
    assert out["sources"] == []
    from rag.followups import GENERAL
    assert out["follow_ups"] == GENERAL[:3]


def test_acronyms_resolve_to_clubs():
    from rag.club_names import ClubNameMatcher

    chunks = load_chunks()
    names = {c["club_id"]: c["name"] for c in chunks}
    matcher = ClubNameMatcher(chunks)
    found = [names[i] for i in matcher.find("What's the difference between CSIT and RMIT Matrix?")]
    assert found == ["Computer Science and Information Technology Society", "RMIT Matrix"]
    assert matcher.find("Is it free?") == []


def test_broad_social_questions():
    from rag.query_hints import is_broad_social

    assert is_broad_social("I'm new to Melbourne and want to make friends.")
    assert is_broad_social("I'm a first year and want to get involved")
    assert not is_broad_social("I'm from Singapore and want to make friends.")
    assert not is_broad_social("I want to meet people who like anime")


def test_background_clubs_only_when_asked():
    from rag.query_hints import put_open_clubs_first

    singapore = {"club_id": "sg", "name": "Singapore Students Association", "category": "Cultural & International",
                 "text": "Description: RMIT students from Singapore can make friends"}
    chess = {"club_id": "chess", "name": "Chess Club", "category": "Social & Special Interest", "text": "Description: chess"}
    clubs = [singapore, chess]
    assert [c["club_id"] for c in put_open_clubs_first("I want to make friends", clubs)] == ["chess", "sg"]
    assert [c["club_id"] for c in put_open_clubs_first("I'm from Singapore, any clubs?", clubs)] == ["sg", "chess"]
    assert [c["club_id"] for c in put_open_clubs_first("any cultural clubs?", clubs)] == ["sg", "chess"]


def test_broad_questions_get_interest_follow_ups():
    from rag.followups import INTERESTS, suggest_follow_ups

    assert suggest_follow_ups("make friends", [{"name": "Chess Club"}], broad=True) == INTERESTS[:3]


def test_five_computing_clubs_are_enriched():
    import csv as _csv

    from rag.config import settings

    with open(settings.data_path, encoding="utf-8-sig") as f:
        rows = [r for r in _csv.DictReader(f) if r["focus_area"] == "Computing"]
    assert {r["acronym"] for r in rows} == {"CSIT", "RISC", "REECE", "Matrix", "SWITCH"}
    assert all(r["description_quality"] == "full" and r["membership_associate"] for r in rows)
    # best-match names, with the other names kept as aliases
    names = {r["acronym"]: r["name"] for r in rows}
    assert names["SWITCH"] == "SWITCH (Society of Women in Technology)"
    assert names["RISC"] == "RMIT Information Security Collective"


def test_computing_group_questions_get_all_five():
    from rag.query_hints import asks_about_computing_clubs

    assert asks_about_computing_clubs("How many computing clubs are there?")
    assert not asks_about_computing_clubs("Is there a chess club?")


def test_citation_repair():
    from rag.citations import repair_citations
    from rag.club_names import ClubNameMatcher

    matcher = ClubNameMatcher(CHUNKS)
    answer = "Try the Chess Club [2]. Their email is listed [1]. The Cyber Club [1] runs CTFs."
    fixed, changes = repair_citations(answer, ["chess", "cyber"], matcher)
    assert fixed == "Try the Chess Club [1]. Their email is listed [1]. The Cyber Club [2] runs CTFs."
    assert changes == 2
    fixed, changes = repair_citations("The Cyber Club [1] runs CTFs.", ["chess"], matcher)
    assert fixed == "The Cyber Club runs CTFs." and changes == 1


def test_internal_notes_are_removed():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("bd", Path(__file__).parents[1] / "data" / "build_dataset.py")
    bd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bd)
    notes = ("Upcoming events: Sip and Paint (7 Oct 2026). Extensive past event history available on Rubric. "
             "On Rubric since 2025. Discord: https://discord.gg/abc.")
    assert bd.clean_notes(notes) == "Upcoming events: Sip and Paint (7 Oct 2026). Discord: https://discord.gg/abc"


def test_filler_words_do_not_match():
    from rag.retrievers.bm25 import tokenize

    assert tokenize("I like harry potter very much") == ["harry", "potter"]
