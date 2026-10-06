# RMIT Clubs Assistant (Team 98)

A chatbot that helps new RMIT students find clubs, compare them and learn how to join. Every answer is built only from verified club information and shows its sources, with links to each club's page, Discord, Instagram and email.

Built for the Work Integrated Learning project in COSC2669/COSC2816 Case Studies in Data Science (RMIT, 2026), following the test-driven RAG approach of [Walert](https://github.com/rmit-ir/walert).

## Why

O-Week and Campus Fest are overwhelming, and club information is scattered across Rubric, Instagram, Discord and Linktree. Students struggle to find their people, while clubs depend on membership for RUSU funding and survival. The assistant gives students one place to ask, in plain language, and points them to the official club channels.

## How it works

```text
Student question
  -> recognise named clubs and acronyms (CSIT, RISC, REECE...)
  -> hybrid retrieval: meaning-based (dense) + keyword (BM25), merged by rank
  -> fairness rules: clubs for a specific culture, faith or politics only when the student mentions it
  -> Llama 3.2 3B (local, via Ollama) answers from those club records only, citing them [1], [2]
  -> citation check, then answer + source cards with links + suggested follow-up questions
```

- **Runs entirely on one laptop:** free model, no API costs, no student data leaves the machine.
- **Declines** questions the club data can't answer instead of guessing.
- **Knowledge base:** 98 RMIT clubs, merged from the team's spreadsheet and the Rubric directory. The five computing clubs (CSIT, RISC, REECE, Matrix, SWITCH) have detailed descriptions, membership tiers and verified links.

## Results

Evaluated on 50 questions in Walert's format: 15 easy, 28 hard (comparisons, eligibility, event dates, lists, paraphrases, typos, fairness) and 7 unanswerable.

**Retrieval** (which clubs are found):

| | Dense | BM25 | **Hybrid (final)** |
|---|---|---|---|
| nDCG@3 | 0.805 | 0.844 | 0.843 |
| Hit@3 (a right club in the top 3) | 0.860 | 0.907 | **0.953** |
| Hard questions, nDCG@3 | 0.748 | 0.768 | **0.781** |
| Real questions wrongly rejected | 0% | 4.7% | **0%** |

**Answers** (final system, hybrid):

| Measure | Result |
|---|---|
| Faithful: every claim backed by the club records (hand-scored) | 82% |
| Correctness, 0–2 (hand-scored) | 1.47 overall (1.80 easy, 1.29 hard) |
| Unanswerable questions handled well | 6 of 7 |
| Citation precision | 88% |
| Median response time | 3.8 s |

Answers were hand-scored against the club records. Full outputs are in `backend/eval/results/`.

**Main limitations:** the model sometimes mixes details between clubs it was given together, invents details for clubs with only a placeholder description (41 of 98), gives incomplete answers to "which clubs…" list questions, and can present past events as upcoming. Most errors trace back to gaps in the club data.

## Run it

You need Python 3.11+, Node.js 22 and [Ollama](https://ollama.com/download). Full step-by-step instructions, including Windows, are in **[QUICK_START.md](QUICK_START.md)**.

```bash
ollama pull llama3.2:3b

# Terminal 1: backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
cp .env.example .env                                # Windows: copy .env.example .env
uvicorn main:app --reload --port 8000

# Terminal 2: website
npm install
npm run dev                                         # open http://localhost:8443
```

## Evaluate it

```bash
cd backend
python evaluate_retrieval.py                       # compare dense / BM25 / hybrid (nDCG, Hit@3, MRR)
python evaluate_retrieval.py --sweep               # tune the relevance thresholds
python eval_end_to_end.py --retriever hybrid       # ask all 50 questions; writes a scoring sheet
python eval_end_to_end.py --summarise eval/results/answers_hybrid.csv
pip install -r requirements-dev.txt && pytest      # unit tests (no model or Ollama needed)
```

## Repository layout

```text
backend/
  main.py                  FastAPI app (/chat, /health, /clubs/search)
  rag/                     pipeline: retrievers/, generator, citations, club_names, query_hints, followups
  data/                    clubs_master.csv (knowledge base) + sources and build_dataset.py
  eval/                    topics.csv, qrels.txt, reference answers, results
  scraper/                 Playwright scraper for the Rubric club directory
  tests/                   pytest unit tests
src/                       React + TypeScript website
QUICK_START.md             setup and run guide
```

## Data and privacy

Club information comes from public RUSU/Rubric pages and club channels, collected by the team. Committee member names for the five computing clubs are included pending a team decision on whether the assistant should show them.

## Team

Group 98, mentored by Lin Tian: Maristel Moralejo-Feliciano, Md Tashfiq Haque Choudhury, Mohamed Ridhwan Mansoor, Spoorthi Mallik Mallikarjuna, Navan Kamalakanthan, Meghana Ramachandraiah.

## Acknowledgements

Our pipeline and evaluation follow Walert:

> Pathiyan Cherumanal, S., Tian, L., Abushaqra, F. M., et al. (2024). *Walert: Putting Conversational Information Seeking Knowledge into Action by Building and Evaluating a Large Language Model-Powered Chatbot.* CHIIR '24. https://doi.org/10.1145/3627508.3638309
