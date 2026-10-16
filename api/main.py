"""HTTP API for the CloudMind React frontend.

Thin wrapper over the existing rag/ functions; no retrieval logic lives here.
Run from the repo root: `uvicorn api.main:app --port 8000`.
"""
import logging
import os
import threading
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import CHROMA_DIR, COLLECTION_NAME, DOCS_DIR
from rag import ingestion, memory, pipeline
from rag.uploads import ALLOWED_UPLOAD_EXTENSIONS, safe_upload_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")
LAST_REFRESH_FILE = os.path.join(CHROMA_DIR, ".last_refresh")
AWS_SOURCES = [source for source, _ in ingestion.AWS_FETCHERS]



@asynccontextmanager
async def lifespan(_app):
    memory.init_db()
    yield


app = FastAPI(title="CloudMind API", version="1.0.0", lifespan=lifespan)

if os.getenv("CLOUDMIND_CORS_ORIGINS"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ["CLOUDMIND_CORS_ORIGINS"].split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong, please try again."}
    )


# ── Models ────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None


class SourceDoc(BaseModel):
    source: str
    type: Optional[str] = None
    title: Optional[str] = None
    snippet: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    source: str
    confidence: float
    docs: list[SourceDoc]


class Session(BaseModel):
    session_id: str
    title: str
    last_active: Optional[str]


class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[str]
    source: Optional[str]
    confidence: Optional[float]


class KBStatus(BaseModel):
    ready: bool
    total: int
    by_source: dict[str, int]
    last_refreshed: Optional[str]
    job: Optional[dict] = None


class UploadedFile(BaseModel):
    name: str
    size: int
    modified: str


# ── Ingestion jobs ────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _running_job():
    for job in _jobs.values():
        if job["status"] == "running":
            return job
    return None


def _run_ingestion(job_id):
    try:
        ingestion.ingest_all()
        with open(LAST_REFRESH_FILE, "w") as f:
            f.write(_now())
        status, error = "succeeded", None
    except Exception:
        logger.exception("Ingestion job %s failed", job_id)
        status, error = "failed", "Ingestion failed, check server logs."
    with _jobs_lock:
        _jobs[job_id].update(status=status, error=error, finished_at=_now())


# ── Helpers ───────────────────────────────────────────────────
def _source_group(source):
    if isinstance(source, str) and source.startswith("aws_"):
        return source
    return "uploads"


def _kb_counts():
    if not ingestion.vectorstore_exists():
        return {}
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return {}
    metas = collection.get(include=["metadatas"])["metadatas"]
    return dict(Counter(_source_group((m or {}).get("source")) for m in metas))


def _doc_title(meta):
    source = meta.get("source", "")
    for key in ("instance_id", "bucket", "function_name", "alarm_name",
                "username", "role_name", "group_name", "vpc_id", "sg_id",
                "log_group", "service", "month"):
        if meta.get(key):
            return str(meta[key])
    if source and not source.startswith("aws_"):
        return os.path.basename(source)
    return None


def _to_source_doc(doc):
    meta = doc.metadata or {}
    return SourceDoc(
        source=_source_group(meta.get("source")),
        type=meta.get("type"),
        title=_doc_title(meta),
        snippet="\n".join(
            line.strip() for line in doc.page_content.splitlines() if line.strip()
        )[:600],
    )


# ── Routes ────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/kb/status", response_model=KBStatus)
def kb_status():
    counts = _kb_counts()
    last = None
    if os.path.exists(LAST_REFRESH_FILE):
        with open(LAST_REFRESH_FILE) as f:
            last = f.read().strip() or None
    elif counts:
        db_file = os.path.join(CHROMA_DIR, "chroma.sqlite3")
        if os.path.exists(db_file):
            last = datetime.fromtimestamp(os.path.getmtime(db_file), timezone.utc).isoformat()
    by_source = {s: counts.get(s, 0) for s in AWS_SOURCES}
    by_source["uploads"] = counts.get("uploads", 0)
    with _jobs_lock:
        job = _running_job()
        job = dict(job) if job else None
    return KBStatus(
        ready=sum(counts.values()) > 0,
        total=sum(counts.values()),
        by_source=by_source,
        last_refreshed=last,
        job=job,
    )


@app.post("/api/kb/refresh", status_code=202)
def kb_refresh():
    with _jobs_lock:
        running = _running_job()
        if running:
            return dict(running)
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {"id": job_id, "status": "running", "error": None,
                         "started_at": _now(), "finished_at": None}
        job = dict(_jobs[job_id])
    threading.Thread(target=_run_ingestion, args=(job_id,), daemon=True).start()
    return job


@app.get("/api/kb/jobs/{job_id}")
def kb_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return dict(job)


@app.get("/api/uploads", response_model=list[UploadedFile])
def list_uploads():
    if not os.path.isdir(DOCS_DIR):
        return []
    files = []
    for name in sorted(os.listdir(DOCS_DIR)):
        path = os.path.join(DOCS_DIR, name)
        if os.path.isfile(path) and not name.startswith("."):
            stat = os.stat(path)
            files.append(UploadedFile(
                name=name, size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            ))
    return files


@app.post("/api/uploads", response_model=list[UploadedFile])
async def upload_files(files: list[UploadFile] = File(...)):
    os.makedirs(DOCS_DIR, exist_ok=True)
    saved = []
    for file in files:
        name = safe_upload_name(file.filename or "")
        ext = os.path.splitext(name)[1].lower()
        if not name or ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file: {file.filename}")
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"File too large: {file.filename}")
        path = os.path.join(DOCS_DIR, name)
        with open(path, "wb") as f:
            f.write(data)
        saved.append(UploadedFile(name=name, size=len(data), modified=_now()))
    return saved


@app.get("/api/sessions", response_model=list[Session])
def list_sessions():
    return [Session(session_id=s, title=t or "New Conversation", last_active=a)
            for s, t, a in memory.get_all_sessions()]


@app.get("/api/sessions/{session_id}/messages", response_model=list[Message])
def session_messages(session_id: str):
    return [Message(role=r, content=c, timestamp=ts, source=src, confidence=conf)
            for r, c, ts, src, conf in memory.get_session_messages(session_id)]


@app.delete("/api/sessions/{session_id}", status_code=204)
def remove_session(session_id: str):
    memory.delete_session(session_id)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not ingestion.vectorstore_exists():
        raise HTTPException(409, "Knowledge base is empty. Refresh AWS data first.")
    session_id = req.session_id or str(uuid.uuid4())
    result = await run_in_threadpool(pipeline.run_pipeline, req.message, session_id)
    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        source=result["source"],
        confidence=float(result["confidence"] or 0.0),
        docs=[_to_source_doc(d) for d in result.get("docs") or []],
    )


# ── Static frontend (production build) ────────────────────────
if os.path.isdir(WEB_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(WEB_DIST, "assets")),
              name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = os.path.join(WEB_DIST, path)
        if path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(WEB_DIST, "index.html"))
