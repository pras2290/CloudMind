import io
import os

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

import api.main as api_main
from rag import memory


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memory, "SQLITE_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setattr(api_main, "DOCS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(api_main, "LAST_REFRESH_FILE", str(tmp_path / ".last_refresh"))
    monkeypatch.setattr(api_main.ingestion, "vectorstore_exists", lambda: True)
    with TestClient(api_main.app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_chat_returns_pipeline_result_and_persists(client, monkeypatch):
    def fake_pipeline(query, session_id):
        memory.create_session(session_id)
        memory.save_message(session_id, "user", query)
        memory.save_message(session_id, "assistant", "3 instances", source="aws_ec2", confidence=0.85)
        memory.update_session_title(session_id, query)
        return {"answer": "3 instances", "confidence": 0.85, "source": "aws_ec2",
                "rewritten_query": query,
                "docs": [Document(page_content="EC2 Instance: web-0",
                                  metadata={"source": "aws_ec2", "type": "ec2_instance",
                                            "instance_id": "i-1"})]}

    monkeypatch.setattr(api_main.pipeline, "run_pipeline", fake_pipeline)
    r = client.post("/api/chat", json={"message": "how many EC2 instances"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "3 instances"
    assert body["source"] == "aws_ec2" and body["confidence"] == 0.85
    assert body["docs"][0] == {"source": "aws_ec2", "type": "ec2_instance",
                               "title": "i-1", "snippet": "EC2 Instance: web-0"}
    sid = body["session_id"]

    sessions = client.get("/api/sessions").json()
    assert [s["session_id"] for s in sessions] == [sid]
    assert sessions[0]["title"] == "how many EC2 instances"
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert client.get("/api/sessions").json() == []
    assert client.get(f"/api/sessions/{sid}/messages").json() == []


def test_chat_error_is_generic(client, monkeypatch):
    def boom(query, session_id):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(api_main.pipeline, "run_pipeline", boom)
    c = TestClient(api_main.app, raise_server_exceptions=False)
    r = c.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Something went wrong, please try again."}


def test_chat_requires_knowledge_base(client, monkeypatch):
    monkeypatch.setattr(api_main.ingestion, "vectorstore_exists", lambda: False)
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 409


def test_upload_sanitizes_name_and_rejects_bad_types(client, tmp_path):
    r = client.post("/api/uploads", files=[
        ("files", ("../../etc/..UI incidents @!.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv"))])
    assert r.status_code == 200
    assert r.json()[0]["name"] == "UI_incidents___.csv"
    assert os.listdir(tmp_path / "uploads") == ["UI_incidents___.csv"]
    assert [f["name"] for f in client.get("/api/uploads").json()] == ["UI_incidents___.csv"]

    r = client.post("/api/uploads", files=[("files", ("evil.sh", io.BytesIO(b"x"), "text/plain"))])
    assert r.status_code == 400


def test_refresh_runs_single_background_job(client, monkeypatch):
    import threading
    gate = threading.Event()
    calls = []

    def fake_ingest():
        calls.append(1)
        gate.wait(5)

    monkeypatch.setattr(api_main.ingestion, "ingest_all", fake_ingest)
    first = client.post("/api/kb/refresh").json()
    second = client.post("/api/kb/refresh").json()
    assert first["id"] == second["id"] and first["status"] == "running"
    gate.set()
    for _ in range(50):
        job = client.get(f"/api/kb/jobs/{first['id']}").json()
        if job["status"] != "running":
            break
        threading.Event().wait(0.05)
    assert job["status"] == "succeeded"
    assert len(calls) == 1
    assert client.get("/api/kb/status").json()["last_refreshed"]
