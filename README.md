# StudySync AI

An AI study desk that turns your own notes into an interactive workspace. Upload a PDF or DOCX, and StudySync builds a private knowledge base you can summarize, ask questions against, quiz yourself on, and track your progress over time.

## Features

- **Grounded summarization** — key concepts, a definitions dictionary, and important points taken only from your document.
- **Ask AI (doubt solving)** — answers your questions using retrieved passages from the uploaded material, with sources.
- **Adaptive quiz** — generates 10 multiple-choice questions per attempt, each tagged with a topic and a skill, and can focus on your weak topics. Runs as a background task so slow local models do not time out the request.
- **Performance dashboard** — topic-wise accuracy, learning progress over time, answer analysis (correct / incorrect / skipped), and a skill-mastery radar.
- **Local-first** — generation and embeddings run on your machine through Ollama, so your documents never leave your device.

## Stack

- React (Vite)
- FastAPI
- SQLite via SQLAlchemy (PostgreSQL also supported through `DATABASE_URL`)
- JWT auth
- Ollama (`llama3.2:3b` + `nomic-embed-text`)
- LangChain + LangGraph
- ChromaDB
- PyPDF / python-docx

## Prerequisites

- Python 3.10+ recommended (3.9 may work if the LangChain packages install)
- Node.js 18+
- [Ollama](https://ollama.com) running locally
- No database server required — the app defaults to SQLite. To use PostgreSQL instead, set `DATABASE_URL` in `.env`.

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

A larger model gives slightly richer answers at the cost of speed. To switch, set `OLLAMA_LLM_MODEL=llama3` in `.env` after `ollama pull llama3`.

## Setup

```bash
cp .env.example .env
```

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If you already have `backend/venv`, activate it and install the new requirements.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, register, upload a PDF or DOCX, then use Summary, Doubts, Quiz, and Performance.

### Uploading from Swagger

The upload endpoints require a bearer token. In `/docs`:

1. Call `POST /auth/register` or `POST /auth/login` with an email and password.
2. Copy the returned `access_token`.
3. Click **Authorize** and enter the token, then click **Authorize** again.
4. Execute `POST /documents/upload` or `POST /upload`.

Calling upload without authorization returns `401 Not authenticated` by design. Do not remove this dependency in development; it keeps uploaded documents associated with the correct user.

### Manual RAG Test

1. Open `http://127.0.0.1:8000/docs`.
2. Register or log in, copy the `access_token`, and click **Authorize**.
3. Run `POST /documents/upload` with a PDF. Confirm the response contains `status: "ready"`, `message: "uploaded successfully"`, and a positive `chunks_stored` value.
4. Copy the returned `id` and run `POST /ask` with this body:

```json
{
	"document_id": 1,
	"question": "What is the main topic in these notes?"
}
```

The response should contain a non-empty `answer` and a `sources` array. Old uploads are retained intentionally; use `DELETE /documents/{document_id}` to remove a test document and its Chroma index.

## API

- `POST /upload` uploads a PDF or DOCX, extracts its text, returns overlapping chunks, and indexes them in ChromaDB.
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `POST /documents/upload`, `GET /documents`, `GET /documents/{id}/summary`
- `POST /ask`
- `POST /quiz`, `POST /quiz/{id}/submit`
- `GET /performance?document_id=`

## Learning flow

Upload → extract/chunk → Ollama embeddings into Chroma → LangGraph summarization → study → grounded Q&A → adaptive quiz → topic and skill scores in SQLite → difficulty `beginner` → `intermediate` → `exam`.

## Tests

The backend ships with a suite of automated tests that mock the AI dependencies, so they run without Ollama:

```bash
cd backend
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Project structure

```
backend/
  app/
    agents/      Summarizer, doubt-solving, and quiz-generation agents
    core/        Settings, security, rate limiting
    db/          Database engine, session, lightweight migrations
    graphs/      LangGraph orchestration
    models/      SQLAlchemy models (users, documents, attempts, scores)
    routers/     FastAPI routers (auth, documents, ask, quiz, performance)
    schemas/     Pydantic request/response schemas
    services/    LLM, embeddings, vector store, ingest, performance
  tests/         Pytest suite (mocks the AI layer)
frontend/
  src/
    components/  Reusable UI (charts, chat, accordion summary, skeletons, toasts, upload)
    pages/       Auth, Workspace
```
