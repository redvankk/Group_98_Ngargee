# Quick Start: run the RMIT Clubs Assistant on your computer

You need three things running: **Ollama** (the language model), the **backend** (port 8000) and the **website** (port 8443). Use two terminal windows.

## One-time setup

Install:
- **Python 3.11 or newer** (3.13 works): https://www.python.org/downloads/ (Windows: tick "Add python.exe to PATH")
- **Node.js 22 LTS**: https://nodejs.org/
- **Ollama**: https://ollama.com/download

Download the model (about 2 GB):

```bash
ollama pull llama3.2:3b
```

Backend, from the project folder:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows Command Prompt: .venv\Scripts\activate.bat
                                   # Windows PowerShell:     .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Website, from the project folder:

```bash
npm install
```

Tip: keep the project outside OneDrive or other synced folders. The Python environment has thousands of files and syncing slows installs down.

## Every time you run it

Make sure the Ollama app is running.

**Terminal 1: backend**

```bash
cd backend
source .venv/bin/activate          # Windows: .venv\Scripts\activate.bat
uvicorn main:app --reload --port 8000
```

Wait for `Application startup complete`. The first start downloads the embedding model and builds the index (1–2 minutes).

**Terminal 2: website**

```bash
npm run dev
```

Open **http://localhost:8443**. The header should show **Online: llama3.2:3b**.

Stop either part with **Ctrl + C**.

## Checks

- http://localhost:8000/health: `retriever` should be `hybrid`, and `llm.model_available` should be `true`
- http://localhost:8000/docs: try `POST /chat` directly
- `python smoke_test.py` (in `backend/`, with the backend running) prints sample answers and timings

## Settings

Edit `backend/.env`, then restart the backend (Ctrl + C, run uvicorn again). `--reload` does not pick up `.env` changes.

| Setting | Default | Notes |
|---|---|---|
| `RETRIEVER` | `hybrid` | `dense`, `bm25` or `hybrid` |
| `DENSE_MIN_SCORE` / `BM25_MIN_SCORE` | `0.24` / `4.0` | Below these, a club doesn't count as relevant |
| `OLLAMA_MODEL` | `llama3.2:3b` | Any model pulled into Ollama |
| `OLLAMA_ENABLED` | `true` | `false` = search-only answers, no model |

## Common problems

| Symptom | Fix |
|---|---|
| Website says "Assistant offline" | The backend isn't running or failed at startup; check Terminal 1. |
| Header says "Search only" | Start the Ollama app, run `ollama pull llama3.2:3b`, refresh. |
| `Activate.ps1 cannot be loaded` | Use Command Prompt, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |
| `Permission denied` writing a results CSV | Close the file in Excel and run again. |
| `Port 8443 is already in use` | Close the other `npm run dev`, or `PORT=5173 npm run dev` (PowerShell: `$env:PORT=5173; npm run dev`). |
| First answer is slow | The model is loading into memory; later answers take about 4 s. |
| Hugging Face "unauthenticated requests" warning | Harmless; it only affects download speed. |

## Updating the club data

Edit `backend/data/Clubs.csv` (team spreadsheet) or the files in `backend/data/five_clubs/`, then:

```bash
cd backend
python data/build_dataset.py
```

Restart the backend; the index rebuilds automatically.

## Optional: re-run the Rubric scraper

```bash
cd backend/scraper
pip install -r requirements.txt
playwright install chromium
python scrape_club_links.py
python scrape_club_profiles.py
python structure_club_profiles.py
```
