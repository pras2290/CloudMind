import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
from datetime import datetime
from config import SQLITE_DB_PATH


# ── Initialize DB ─────────────────────────────────────────────
def init_db():
    """Create SQLite tables if not exists."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT,
            last_active TEXT,
            title TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT,
            source TEXT,
            confidence REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    conn.commit()
    conn.close()


# ── Session management ────────────────────────────────────────
def create_session(session_id, title="New Conversation"):
    """Create a new session."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT OR IGNORE INTO sessions VALUES (?, ?, ?, ?)",
        (session_id, now, now, title)
    )
    conn.commit()
    conn.close()


def get_all_sessions():
    """Get all sessions ordered by last active."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_id, title, last_active FROM sessions ORDER BY last_active DESC"
    )
    sessions = cursor.fetchall()
    conn.close()
    return sessions


def update_session_title(session_id, title):
    """Update session title based on first question."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET title=? WHERE session_id=?",
        (title[:50], session_id)
    )
    conn.commit()
    conn.close()


def update_session_active(session_id):
    """Update last active timestamp."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET last_active=? WHERE session_id=?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()
    conn.close()


def delete_session(session_id):
    """Delete session and all its messages."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()


# ── Message management ────────────────────────────────────────
def save_message(session_id, role, content, source="", confidence=0.0):
    """Save a message to the session."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content, timestamp, source, confidence) VALUES (?,?,?,?,?,?)",
        (session_id, role, content, datetime.now().isoformat(), source, confidence)
    )
    conn.commit()
    conn.close()
    update_session_active(session_id)


def get_session_messages(session_id):
    """Get all messages for a session."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, timestamp, source, confidence FROM messages WHERE session_id=? ORDER BY id",
        (session_id,)
    )
    messages = cursor.fetchall()
    conn.close()
    return messages


def get_chat_history(session_id, last_n=6):
    """Get last N messages for LLM context."""
    messages = get_session_messages(session_id)
    history = []
    for role, content, _, _, _ in messages[-last_n:]:
        history.append({"role": role, "content": content})
    return history


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("DB initialized")

    # Test session
    create_session("test-session-001", "Test Conversation")
    print("Session created")

    # Test messages
    save_message("test-session-001", "user", "What is my AWS cost?")
    save_message("test-session-001", "assistant", "Your AWS cost last month was $12.30", source="aws_cost_explorer", confidence=0.85)

    # Retrieve
    messages = get_session_messages("test-session-001")
    print(f"\nMessages in session: {len(messages)}")
    for msg in messages:
        print(f"{msg[0]}: {msg[1]}")

    # All sessions
    sessions = get_all_sessions()
    print(f"\nAll sessions: {sessions}")

    # Chat history for LLM
    history = get_chat_history("test-session-001")
    print(f"\nChat history: {history}")

    # Cleanup
    delete_session("test-session-001")
    print("\nTest session deleted")