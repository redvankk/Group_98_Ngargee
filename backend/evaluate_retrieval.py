"""Compare retrievers on the Walert-style question set.

Usage:  python evaluate_retrieval.py [--retrievers dense bm25 hybrid]

Reads eval/topics.csv and eval/qrels.txt (same layout as Walert: question ids,
graded relevance 0-2 per club). Reports, per retriever:
  nDCG@1/3/5, Hit@3 and MRR  on answerable questions
  Rejected                    share of unanswerable questions where no club passed
                              the relevance threshold (the assistant would decline)
  False rejects               share of answerable questions wrongly declined
Results are also broken down by question type, and a TREC run file per
retriever is written to eval/runs/ for ranx/trec_eval.

Club names in a question are resolved the same way as in the app
(rag/club_names.py), so these numbers reflect what the assistant actually sees.
"""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

from rag.club_names import ClubNameMatcher
from rag.config import RETRIEVERS
from rag.knowledge_base import load_chunks
from rag.query_hints import asks_about_computing_clubs
from rag.service import build_club_records, is_near_empty, _name_in_question
from rag.retrievers import BM25Retriever, DenseRetriever, HybridRetriever

BASE = Path(__file__).resolve().parent
TOPICS = BASE / "eval" / "topics.csv"
QRELS = BASE / "eval" / "qrels.txt"
RUNS_DIR = BASE / "eval" / "runs"
DEPTH = 10
COMPUTING: list[str] = []  # clubs tagged Computing (filled in main)
RECORDS: dict[str, dict] = {}  # full club records (filled in main)


def load_eval():
    with TOPICS.open(encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    for line in QRELS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            qid, _, club, rel = line.split()
            qrels[qid][club] = int(rel)
    return questions, qrels


def ndcg(ranked: list[str], rels: dict[str, int], k: int) -> float:
    dcg = sum(rels.get(c, 0) / math.log2(i + 2) for i, c in enumerate(ranked[:k]))
    ideal = sorted(rels.values(), reverse=True)[:k]
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def build(names: list[str], chunks: list[dict]) -> dict:
    dense = DenseRetriever() if {"dense", "hybrid"} & set(names) else None
    bm25 = BM25Retriever() if {"bm25", "hybrid"} & set(names) else None
    if dense:
        dense.build(chunks)
    if bm25:
        bm25.build(chunks)
    built = {"dense": dense, "bm25": bm25}
    if "hybrid" in names:
        hybrid = HybridRetriever(dense=dense, bm25=bm25)
        hybrid.chunks = chunks
        built["hybrid"] = hybrid
    return {n: built[n] for n in names}


def search(retriever, matcher: ClubNameMatcher, question: str) -> list[dict]:
    """Named clubs first (as in the app), then retrieval results."""
    named = matcher.find(question)
    if asks_about_computing_clubs(question):
        named += [c for c in COMPUTING if c not in named]
    results = retriever.search(question, top_k=DEPTH + len(named))
    by_id = {r["club_id"]: r for r in results}
    top = max((r["score"] for r in results), default=1.0)
    ranked = [{"club_id": c, "score": by_id.get(c, {"score": top})["score"], "relevant": True} for c in named]
    for r in results:
        record = RECORDS.get(r["club_id"], {})
        if r["club_id"] in named or (is_near_empty(record) and not _name_in_question(record, question)):
            continue  # same rule as the app: near-empty clubs only when named
        ranked.append(r)
    return ranked[:DEPTH]


def sweep(questions, qrels, matcher, chunks, names) -> None:
    """For each threshold: share of unanswerable questions declined vs answerable
    questions wrongly declined. Pick the threshold with the best balance and set
    DENSE_MIN_SCORE / BM25_MIN_SCORE in .env (hybrid uses both)."""
    retrievers = build(names, chunks)
    grids = {"dense": [0.15, 0.20, 0.24, 0.28, 0.32, 0.36, 0.40, 0.45],
             "bm25": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]}
    for name, retriever in retrievers.items():
        best = []  # (answerable?, has named club, top retrieval score)
        for q in questions:
            named = bool(matcher.find(q["question"])) or asks_about_computing_clubs(q["question"])
            results = search(retriever, matcher, q["question"])
            top = max((r["score"] for r in results if r["club_id"] not in matcher.find(q["question"])), default=0.0)
            best.append((bool(qrels.get(q["question_id"])), named, top))
        print(f"\nThreshold sweep: {name}")
        print(f"{'threshold':>9} {'Rejected':>9} {'False rej.':>10}")
        for t in grids[name]:
            rej = [not named and top < t for ans, named, top in best if not ans]
            false = [not named and top < t for ans, named, top in best if ans]
            print(f"{t:>9.2f} {sum(rej) / len(rej):>9.3f} {sum(false) / len(false):>10.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval")
    parser.add_argument("--retrievers", nargs="+", choices=RETRIEVERS, default=list(RETRIEVERS))
    parser.add_argument("--sweep", action="store_true",
                        help="show how dense/BM25 relevance thresholds trade off declines (for tuning .env)")
    args = parser.parse_args()

    questions, qrels = load_eval()
    chunks = load_chunks()
    known = {c["club_id"] for c in chunks}
    missing = {c for rels in qrels.values() for c in rels} - known
    if missing:
        print(f"WARNING: qrels mention clubs not in the data: {sorted(missing)[:5]}\n")

    matcher = ClubNameMatcher(chunks)
    RECORDS.update(build_club_records(chunks))
    COMPUTING.extend(dict.fromkeys(c["club_id"] for c in chunks if "Type: Computing" in c["text"]))
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    header = f"{'retriever':<9} {'nDCG@1':>7} {'nDCG@3':>7} {'nDCG@5':>7} {'Hit@3':>6} {'MRR':>6} {'Rejected':>9} {'False rej.':>10}"
    print(header)
    by_type_all = {}
    by_level_all = {}
    for name, retriever in build(args.retrievers, chunks).items():
        scores = defaultdict(list)
        by_type = defaultdict(list)
        by_level = defaultdict(list)
        rejected, false_rejects, run = [], [], []
        for q in questions:
            qid, rels = q["question_id"], qrels.get(q["question_id"], {})
            results = search(retriever, matcher, q["question"])
            ranked = [r["club_id"] for r in results]
            declined = not any(r["relevant"] for r in results)
            run += [f"{qid} Q0 {r['club_id']} {i} {r['score']:.6f} clubs.{name}" for i, r in enumerate(results, 1)]

            if not rels:  # unanswerable
                rejected.append(declined)
                continue
            false_rejects.append(declined)
            for k in (1, 3, 5):
                scores[f"ndcg{k}"].append(ndcg(ranked, rels, k))
            scores["hit3"].append(any(c in rels for c in ranked[:3]))
            first = next((i for i, c in enumerate(ranked, 1) if c in rels), None)
            scores["mrr"].append(1 / first if first else 0.0)
            by_type[q["question_type"]].append(ndcg(ranked, rels, 3))
            by_level[q.get("difficulty", "all")].append(ndcg(ranked, rels, 3))

        (RUNS_DIR / f"{name}.txt").write_text("\n".join(run) + "\n", encoding="utf-8")
        mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
        print(
            f"{name:<9} {mean(scores['ndcg1']):>7.3f} {mean(scores['ndcg3']):>7.3f} {mean(scores['ndcg5']):>7.3f} "
            f"{mean(scores['hit3']):>6.3f} {mean(scores['mrr']):>6.3f} {mean(rejected):>9.3f} {mean(false_rejects):>10.3f}"
        )
        by_type_all[name] = {t: mean(v) for t, v in by_type.items()}
        by_level_all[name] = {t: mean(v) for t, v in by_level.items()}

    if args.sweep:
        sweep(questions, qrels, matcher, chunks, [n for n in args.retrievers if n != "hybrid"])

    types = sorted({t for d in by_type_all.values() for t in d})
    print("\nnDCG@3 by question type")
    print(f"{'retriever':<9} " + " ".join(f"{t:>15}" for t in types))
    for name, d in by_type_all.items():
        print(f"{name:<9} " + " ".join(f"{d.get(t, float('nan')):>15.3f}" for t in types))
    levels = sorted({t for d in by_level_all.values() for t in d})
    print("\nnDCG@3 by difficulty")
    print(f"{'retriever':<9} " + " ".join(f"{t:>8}" for t in levels))
    for name, d in by_level_all.items():
        print(f"{name:<9} " + " ".join(f"{d.get(t, float('nan')):>8.3f}" for t in levels))
    print(f"\n{len(questions)} questions. Run files: {RUNS_DIR.relative_to(BASE)}/")


if __name__ == "__main__":
    main()
