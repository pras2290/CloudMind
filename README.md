# CloudMind

AWS intelligence assistant: ingests your AWS account (EC2, S3, Lambda, CloudWatch, IAM, Cost Explorer) and uploaded runbooks into a Chroma vector store, and answers questions with hybrid retrieval (vector + BM25 + cross-encoder reranking) and OpenAI.

## Layout

| Path | What |
|---|---|
| `fetchers/` | AWS fetchers and shared helpers (`fetchers/common.py`) |
| `rag/` | Ingestion, retrieval, pipeline, SQLite chat memory |
| `api/` | FastAPI server used by the React UI |
| `web/` | React + Vite + TypeScript frontend |
| `app.py` | Legacy Streamlit UI (kept until the React UI is fully adopted) |

## Setup

Requires Python 3.11+ and Node 20+.

```bash
python -m venv venv
venv/bin/pip install -r requirements-dev.txt
(cd web && npm ci)
```

Create `.env` in the repo root:

```
OPENAI_API_KEY=sk-...
AWS_REGION=us-east-1
# Optional: omit to use the default boto3 credential chain (IAM role, SSO, ~/.aws)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

Run everything from the repo root (modules use package imports, e.g. `python -m rag.ingestion`).

## Development

```bash
venv/bin/uvicorn api.main:app --reload --port 8000   # API
(cd web && npm run dev)                              # UI on http://localhost:5173, proxies /api to :8000
```

Open the Knowledge base page and click **Refresh AWS data** to build the index before chatting.

## Production

```bash
(cd web && npm run build)
venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The API serves the built UI from `web/dist` on the same origin. To call the API from another origin, set `CLOUDMIND_CORS_ORIGINS` (comma-separated).

The legacy Streamlit UI still works: `venv/bin/streamlit run app.py`.

## Tests

```bash
venv/bin/python -m pytest tests
(cd web && npm run lint && npm run typecheck && npm test)
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness |
| GET | `/api/kb/status` | Index readiness, chunk counts per source, running refresh job |
| POST | `/api/kb/refresh` | Start a background `ingest_all()` (one at a time) |
| GET | `/api/kb/jobs/{id}` | Refresh job status |
| GET / POST | `/api/uploads` | List / upload documents (pdf, docx, csv, txt; 25 MB max) |
| GET | `/api/sessions` | Conversations |
| GET | `/api/sessions/{id}/messages` | Conversation messages |
| DELETE | `/api/sessions/{id}` | Delete a conversation |
| POST | `/api/chat` | Run `run_pipeline`; returns answer, source, confidence and retrieved snippets |
