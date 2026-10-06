# RMIT Clubs RAG backend

## Pipeline

```text
question
  -> rewrite_query        short follow-ups get the previous question appended
  -> retriever            dense | bm25 | hybrid, one best chunk per club
  -> relevance check      no chunk above the threshold -> assistant declines
  -> Ollama (llama3.2:3b) answers from numbered sources only, cites [1], [2]
  -> response             answer + numbered sources + mode + timings
```

| File | Role |
|---|---|
| `rag/config.py` | All settings, read from `backend/.env` |
| `rag/data_loader.py` | Reads `data/clubs_master.csv` (or the original `Clubs.csv`) |
| `rag/chunking.py` | Splits each club into an overview chunk and a membership/contact chunk |
| `rag/knowledge_base.py` | Loads every chunk |
| `rag/retrievers/` | `dense.py` (Sentence Transformers), `bm25.py` (Okapi BM25), `hybrid.py` (reciprocal rank fusion) |
| `rag/generator.py` | Prompt, Ollama call, fallback answers |
| `rag/service.py` | Runs the pipeline and times each step |
| `main.py` | FastAPI app |

## Setup (Python 3.11)

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
uvicorn main:app --reload --port 8000
```

Also install Ollama and run `ollama pull llama3.2:3b`. The first start downloads the embedding model (~90 MB) and builds the index. Open http://localhost:8000/health: `llm.model_available` should be `true`.

## Configuration

See `.env.example`. The settings you are most likely to change:

| Setting | Default | Notes |
|---|---|---|
| `RETRIEVER` | `dense` | `dense`, `bm25` or `hybrid` |
| `DENSE_MIN_SCORE` | `0.24` | Cosine threshold for "relevant" |
| `BM25_MIN_SCORE` | `4.0` | BM25 threshold (different scale from cosine) |
| `OLLAMA_ENABLED` | `true` | `false` = retrieval-only answers |
| `OLLAMA_MODEL` | `llama3.2:3b` | Any model pulled into Ollama |
| `OLLAMA_TEMPERATURE` | `0.1` | Low = more factual and repeatable |
| `OLLAMA_NUM_CTX` | `4096` | Context window; keep above ~2,500 tokens |

Both thresholds are starting guesses: tune them with unanswerable questions in the evaluation set.

## Response modes

| `mode` | Meaning |
|---|---|
| `rag` | LLM answer grounded in the numbered sources |
| `no-match` | No relevant chunk found; the assistant declines |
| `retrieval-only` | Ollama disabled; extractive answer |
| `llm-error` | Ollama failed or timed out; extractive answer (see server log) |

## Evaluation and tests

```bash
python evaluate_retrieval.py            # nDCG, Hit@3, MRR, unanswerable rejection, per retriever + TREC run files
python eval_end_to_end.py               # full answers: decline rate, citation accuracy, timing, hand-scoring sheet
python smoke_test.py                    # sample questions against the running API
pip install -r requirements-dev.txt && pytest   # unit tests, no model or Ollama needed
```

The question set is `eval/topics.csv` + `eval/qrels.txt` (Walert layout). It is a
draft: the team should review the questions and relevance judgements.

## Updating data

The app reads `data/clubs_master.csv`, built from the team spreadsheet
(`data/Clubs.csv`) and the Rubric scrape. After editing either source:

```bash
python data/build_dataset.py   # rebuilds clubs_master.csv and collection files
```

Then restart the API; the dense index re-embeds automatically. See `data/README.md`.
`/admin/reindex` is disabled unless `ALLOW_REINDEX=true`.
