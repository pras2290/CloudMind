import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)

# One shared connection per process, serialized by a lock. Streamlit runs
# reruns on different threads, so check_same_thread must be disabled.
_lock = threading.RLock()
_conn = None
_conn_path = None


def _get_conn():
    global _conn, _conn_path
    if _conn is None or _conn_path != SQLITE_DB_PATH:
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(
            SQLITE_DB_PATH, check_same_thread=False, timeout=30
        )
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=30000")
        _conn_path = SQLITE_DB_PATH
    return _conn


@contextmanager
def _cursor():
    """Locked cursor that commits on success and rolls back on error."""
    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


# ── Initialize DB ─────────────────────────────────────────────
def init_db():
    """Create SQLite tables if not exists."""
    with _cursor() as cursor:
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


# ── Session management ────────────────────────────────────────
def create_session(session_id, title="New Conversation"):
    """Create a new session."""
    now = datetime.now().isoformat()
    with _cursor() as cursor:
        cursor.execute(
            "INSERT OR IGNORE INTO sessions VALUES (?, ?, ?, ?)",
            (session_id, now, now, title)
        )


def get_all_sessions():
    """Get all sessions ordered by last active."""
    with _cursor() as cursor:
        cursor.execute(
            "SELECT session_id, title, last_active FROM sessions ORDER BY last_active DESC"
        )
        return cursor.fetchall()


def update_session_title(session_id, title):
    """Update session title based on first question."""
    with _cursor() as cursor:
        cursor.execute(
            "UPDATE sessions SET title=? WHERE session_id=?",
            (title[:50], session_id)
        )


def update_session_active(session_id):
    """Update last active timestamp."""
    with _cursor() as cursor:
        cursor.execute(
            "UPDATE sessions SET last_active=? WHERE session_id=?",
            (datetime.now().isoformat(), session_id)
        )


def delete_session(session_id):
    """Delete session and all its messages."""
    with _cursor() as cursor:
        cursor.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))


# ── Message management ────────────────────────────────────────
def save_message(session_id, role, content, source="", confidence=0.0):
    """Save a message to the session."""
    with _cursor() as cursor:
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, timestamp, source, confidence) VALUES (?,?,?,?,?,?)",
            (session_id, role, content, datetime.now().isoformat(), source, confidence)
        )
    update_session_active(session_id)


def get_session_messages(session_id):
    """Get all messages for a session."""
    with _cursor() as cursor:
        cursor.execute(
            "SELECT role, content, timestamp, source, confidence FROM messages WHERE session_id=? ORDER BY id",
            (session_id,)
        )
        return cursor.fetchall()


def get_chat_history(session_id, last_n=6):
    """Get last N messages for LLM context."""
    messages = get_session_messages(session_id)
    history = []
    for role, content, _, _, _ in messages[-last_n:]:
        history.append({"role": role, "content": content})
    return history


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()
    logger.info("DB initialized")

    # Test session
    create_session("test-session-001", "Test Conversation")
    logger.info("Session created")

    # Test messages
    save_message("test-session-001", "user", "What is my AWS cost?")
    save_message("test-session-001", "assistant", "Your AWS cost last month was $12.30", source="aws_cost_explorer", confidence=0.85)

    # Retrieve
    messages = get_session_messages("test-session-001")
    logger.info("\nMessages in session: %d", len(messages))
    for msg in messages:
        logger.info("%s: %s", msg[0], msg[1])

    # All sessions
    sessions = get_all_sessions()
    logger.info("\nAll sessions: %s", sessions)

    # Chat history for LLM
    history = get_chat_history("test-session-001")
    logger.info("\nChat history: %s", history)

    # Cleanup
    delete_session("test-session-001")
    logger.info("\nTest session deleted")
