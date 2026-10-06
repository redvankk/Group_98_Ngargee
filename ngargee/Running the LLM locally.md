# Running the LLM locally

This project uses **Ollama** to run the local LLM and **Llama 3.2 3B** as the generation model.

The model itself is **not stored in this GitHub repository**. Each team member who wants to run the full chatbot locally must install Ollama and download the model on their own machine.

---

## 1. Install Ollama

Download Ollama from:

https://ollama.com/

Install it normally for your operating system.

Check that Ollama is available:

```bash
ollama --version
```

If a version number is shown, Ollama is installed correctly.

---

## 2. Download the project LLM

The current project model is:

```text
llama3.2:3b
```

Download it with:

```bash
ollama pull llama3.2:3b
```

This may take a few minutes because the model is downloaded to your local machine.

Check that the model is installed:

```bash
ollama list
```

You should see `llama3.2:3b` in the output.

---

## 3. Test the model by itself

Run:

```bash
ollama run llama3.2:3b
```

You will get an interactive prompt in the same terminal window.

Try something simple such as:

```text
Say hello in one sentence.
```

If the model replies, Ollama and Llama 3.2 3B are working.

Exit the interactive chat with:

```text
/bye
```

You do **not** need to keep this interactive chat open while running the RAG backend.

---

## 4. Ollama local server

Ollama normally exposes its local API at:

```text
http://localhost:11434
```

The FastAPI backend communicates with Ollama through this local API.

The normal local architecture is:

```text
React/Vite frontend
        ↓
FastAPI backend
        ↓
RAG retrieval
        ↓
Ollama local API
        ↓
Llama 3.2 3B
```

---

## 5. Configure the backend

Inside the `backend` folder, create a local `.env` file if one does not already exist.

Use settings similar to:

```env
OLLAMA_ENABLED=true
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

The `.env` file is local configuration and should **not** be committed to GitHub.

The repository contains `.env.example` files that can be used as a reference.

---

## 6. Install Python dependencies

From the repository root:

```bash
cd backend
```

Create and activate a Python virtual environment.

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The backend uses the Ollama Python client to call the local Ollama service.

---

## 7. Build the RAG index

Before starting the chatbot backend, build the current knowledge-base index:

```bash
python build_index.py
```

This creates the stored document embeddings used for retrieval.

The LLM is **not trained on this data**. The RAG system retrieves relevant chunks and sends them to Llama 3.2 3B at question time.

---

## 8. Start the FastAPI backend

From `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

Check the backend health page:

```text
http://localhost:8000/health
```

When Ollama is correctly configured, the response should show something similar to:

```json
{
  "status": "ok",
  "llm_enabled": true,
  "generation_model": "llama3.2:3b",
  "mode": "semantic-rag+ollama"
}
```

The exact club/chunk counts can change as the dataset changes.

---

## 9. Start the frontend

Open a second terminal at the repository root:

```bash
npm install
npm run dev
```

The frontend currently normally runs at:

```text
http://localhost:8443/
```

Use whatever URL Vite prints in the terminal if it differs.

The full local system is then:

```text
Frontend  → http://localhost:8443
FastAPI   → http://localhost:8000
Ollama    → http://localhost:11434
```

---

## 10. What happens when a user asks a question?

The LLM does not search the database directly.

The flow is:

```text
User question
    ↓
FastAPI
    ↓
Sentence Transformer creates a query embedding
    ↓
Semantic search finds the most relevant club chunks
    ↓
Question + retrieved chunks are sent to Ollama
    ↓
Llama 3.2 3B writes a grounded answer
    ↓
FastAPI returns the answer + sources
    ↓
React website displays the result
```

---

## 11. Common problems

### `ollama: command not found`

Ollama is not installed correctly or is not available in your PATH.

Install/reopen Ollama, then open a new terminal and run:

```bash
ollama --version
```

### Model not found

Run:

```bash
ollama pull llama3.2:3b
```

Then verify:

```bash
ollama list
```

### Backend shows `llm_enabled: false`

Check the backend `.env` file:

```env
OLLAMA_ENABLED=true
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

Restart FastAPI after changing `.env`.

### Ollama generation fails

Check whether Ollama is running and whether the model is installed:

```bash
ollama list
ollama ps
```

Try the model directly:

```bash
ollama run llama3.2:3b
```

If the model works interactively but FastAPI still fails, check the backend terminal for the exact error.

### Port 8000 already in use

On macOS/Linux:

```bash
lsof -i :8000
```

Stop the old process or restart the existing backend instead of starting a second copy.

---

## 12. Optional: unload the model

If you are finished testing and want to free memory:

```bash
ollama stop llama3.2:3b
```

On laptops this can reduce RAM usage and heat when the LLM is no longer needed.

---

## Summary

Each team member who wants to run the full LLM-enabled chatbot locally needs to:

1. Install Ollama
2. Run `ollama pull llama3.2:3b`
3. Configure `backend/.env`
4. Install backend dependencies
5. Run `python build_index.py`
6. Start FastAPI
7. Start the React/Vite frontend

The GitHub repository contains the code, but the Ollama model is downloaded separately on each developer's machine.
