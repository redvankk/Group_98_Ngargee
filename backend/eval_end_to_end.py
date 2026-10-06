"""End-to-end evaluation: ask every question in eval/topics.csv and score the answers.

Usage (from backend/, with Ollama running; the API does not need to be running):
    python eval_end_to_end.py                 # uses RETRIEVER from .env
    python eval_end_to_end.py --retriever hybrid
    python eval_end_to_end.py --limit 10      # quick trial run

Automatic measures (Walert-style plus attribution):
  Answered rate            answerable questions that got an answer (not declined)
  Correct declines         unanswerable questions the assistant declined
  Citation precision       cited clubs that are relevant in qrels.txt
  Citation hit rate        answers citing at least one relevant club
  Response time            mean / median / 90th percentile (seconds)
  ROUGE-L vs reference     only if eval/reference_answers.csv exists
                           (columns: question_id, reference_answer)

It also writes eval/results/answers_<retriever>.csv with every answer and two
empty columns for the team to score by hand:
  faithful (0/1)   every claim is supported by the cited club records
  correct  (0-2)   0 wrong/unhelpful, 1 partly right, 2 fully answers the question
Run  python eval_end_to_end.py --summarise eval/results/answers_<retriever>.csv
after filling them in to add those scores to the summary.
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
EVAL = BASE / "eval"
RESULTS = EVAL / "results"
REFERENCES = EVAL / "reference_answers.csv"

DECLINE = re.compile(
    r"\b(i (don't|do not|couldn't|could not|can't|cannot) (have|find|answer|help)|"
    r"no information|not (in|part of) (the|my)|i'm not able|i am not able|"
    r"don't have (that|any|enough) information)\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ data

def load_questions() -> list[dict]:
    with (EVAL / "topics.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_qrels() -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    for line in (EVAL / "qrels.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            qid, _, club, rel = line.split()
            qrels[qid][club] = int(rel)
    return qrels


def load_references() -> dict[str, str]:
    if not REFERENCES.exists():
        return {}
    with REFERENCES.open(encoding="utf-8-sig") as f:
        return {r["question_id"]: r["reference_answer"] for r in csv.DictReader(f) if r.get("reference_answer")}


# ------------------------------------------------------------------ scoring

def is_decline(row: dict) -> bool:
    """Declined = no club cited, or the answer says it can't help."""
    return row["mode"] == "no-match" or not row["cited_ids"] or bool(DECLINE.search(row["answer"][:200]))


def rouge_l(candidate: str, reference: str) -> float:
    a = re.findall(r"\w+", candidate.lower())
    b = re.findall(r"\w+", reference.lower())
    if not a or not b:
        return 0.0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
        prev = cur
    lcs = prev[-1]
    p, r = lcs / len(a), lcs / len(b)
    return 2 * p * r / (p + r) if p + r else 0.0


def pct(values: list[bool | float]) -> str:
    return f"{100 * sum(values) / len(values):.1f}%" if values else "n/a"


def summarise(rows: list[dict], qrels: dict, references: dict) -> None:
    answerable = [r for r in rows if qrels.get(r["question_id"])]
    unanswerable = [r for r in rows if not qrels.get(r["question_id"])]

    cited_precision, cited_hit = [], []
    for r in answerable:
        rel = qrels[r["question_id"]]
        cited = [c for c in r["cited_ids"].split(";") if c]
        if cited:
            cited_precision.append(sum(c in rel for c in cited) / len(cited))
            cited_hit.append(any(c in rel for c in cited))

    times = [float(r["seconds"]) for r in rows if r["seconds"]]
    print(f"\n=== {len(rows)} questions ({len(answerable)} answerable, {len(unanswerable)} unanswerable) ===")
    print(f"Answered rate (answerable)      {pct([not is_decline(r) for r in answerable])}")
    print(f"Correct declines (unanswerable) {pct([is_decline(r) for r in unanswerable])}")
    print(f"Citation precision              {pct(cited_precision)}")
    print(f"Citation hit rate               {pct(cited_hit)}  (of answers that cite something)")
    if times:
        times.sort()
        p90 = times[min(len(times) - 1, int(0.9 * len(times)))]
        print(f"Response time (s)               mean {statistics.mean(times):.1f} | "
              f"median {statistics.median(times):.1f} | p90 {p90:.1f}")
    fixes = [int(r.get("citation_fixes") or 0) for r in rows]
    print(f"Citations corrected             {sum(fixes)} in {sum(1 for f in fixes if f)} answers")
    modes = defaultdict(int)
    for r in rows:
        modes[r["mode"]] += 1
    print(f"Modes                           {dict(modes)}")

    if references:
        scored = [rouge_l(r["answer"], references[r["question_id"]]) for r in rows if r["question_id"] in references]
        print(f"ROUGE-L F1 vs reference         {statistics.mean(scored):.3f}  ({len(scored)} questions)")

    faithful = [int(r["faithful"]) for r in rows if str(r.get("faithful", "")).strip() in {"0", "1"}]
    correct = [int(r["correct"]) for r in answerable if str(r.get("correct", "")).strip() in {"0", "1", "2"}]
    if faithful:
        print(f"Faithful (hand-scored)          {pct(faithful)}  ({len(faithful)} scored)")
    if correct:
        print(f"Correctness (hand-scored, 0-2)  mean {statistics.mean(correct):.2f}  ({len(correct)} scored)")

    by_type = defaultdict(list)
    for r in answerable:
        by_type[r["question_type"]].append(not is_decline(r))
    print("Answered rate by type           " + ", ".join(f"{t}: {pct(v)}" for t, v in sorted(by_type.items())))
    by_level = defaultdict(list)
    for r in answerable:
        by_level[r.get("difficulty") or "all"].append(not is_decline(r))
    print("Answered rate by difficulty     " + ", ".join(f"{t}: {pct(v)}" for t, v in sorted(by_level.items())))
    correct_by_level = defaultdict(list)
    for r in answerable:
        if str(r.get("correct", "")).strip() in {"0", "1", "2"}:
            correct_by_level[r.get("difficulty") or "all"].append(int(r["correct"]))
    if correct_by_level:
        print("Correctness by difficulty       " + ", ".join(
            f"{t}: {statistics.mean(v):.2f}" for t, v in sorted(correct_by_level.items())))


# ------------------------------------------------------------------ run

FIELDS = [
    "question_id", "topic_id", "question_type", "difficulty", "question", "answer", "mode", "retriever",
    "cited_ids", "cited_names", "relevant_ids", "citation_fixes", "seconds", "faithful", "correct", "comments",
]


def run(retriever: str | None, limit: int | None) -> Path:
    logging.basicConfig(level="WARNING")
    from rag import service
    from rag.config import settings

    name = retriever or settings.retriever
    service.init(retriever_name=name)
    questions = load_questions()[: limit or None]
    qrels = load_qrels()

    rows = []
    for i, q in enumerate(questions, 1):
        started = time.perf_counter()
        out = service.answer_question(q["question"], [], top_k=4)
        seconds = time.perf_counter() - started
        rows.append({
            "question_id": q["question_id"],
            "topic_id": q["topic_id"],
            "question_type": q["question_type"],
            "difficulty": q.get("difficulty", ""),
            "question": q["question"],
            "answer": out["answer"],
            "mode": out["mode"],
            "retriever": out["retriever"],
            "cited_ids": ";".join(s["id"] for s in out["sources"]),
            "cited_names": "; ".join(s["name"] for s in out["sources"]),
            "relevant_ids": ";".join(qrels.get(q["question_id"], {})),
            "citation_fixes": out.get("citation_fixes", 0),
            "seconds": f"{seconds:.2f}",
            "faithful": "", "correct": "", "comments": "",
        })
        print(f"[{i}/{len(questions)}] {q['question_id']} {out['mode']:<14} {seconds:5.1f}s  {q['question'][:60]}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"answers_{name}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summarise(rows, qrels, load_references())
    print(f"\nAnswers saved to {path.relative_to(BASE)}; fill in 'faithful' and 'correct', then run with --summarise.")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end evaluation")
    parser.add_argument("--retriever", choices=["dense", "bm25", "hybrid"])
    parser.add_argument("--limit", type=int, help="only ask the first N questions")
    parser.add_argument("--summarise", type=Path, help="re-summarise a hand-scored answers CSV")
    args = parser.parse_args()

    if args.summarise:
        with args.summarise.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        summarise(rows, load_qrels(), load_references())
    else:
        run(args.retriever, args.limit)


if __name__ == "__main__":
    main()
