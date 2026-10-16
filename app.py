import logging
import os
import uuid
import streamlit as st
from config import DOCS_DIR
from rag.pipeline import run_pipeline
from rag.memory import (
    init_db, get_all_sessions, get_session_messages,
    create_session, delete_session
)
from rag.ingestion import ingest_all, load_vectorstore, vectorstore_exists
from rag.uploads import safe_upload_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="CloudMind",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Initialize ────────────────────────────────────────────────
init_db()

# ── Session state ─────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ingested" not in st.session_state:
    st.session_state.ingested = vectorstore_exists()

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.title("☁️ CloudMind")
    st.caption("AWS Intelligence Platform")
    st.divider()

    # Data ingestion
    st.subheader("Knowledge Base")
    if st.button("🔄 Refresh AWS Data", use_container_width=True):
        with st.spinner("Fetching AWS data and indexing..."):
            ingest_all()
            st.session_state.ingested = True
        st.success("Knowledge base updated!")

    # File upload
    st.subheader("Upload Documents")
    uploaded_files = st.file_uploader(
        "Runbooks, KEDB, SOPs",
        accept_multiple_files=True,
        type=["pdf", "docx", "csv", "txt"]
    )
    if uploaded_files:
        os.makedirs(DOCS_DIR, exist_ok=True)
        for file in uploaded_files:
            safe_name = safe_upload_name(file.name)
            if not safe_name:
                continue
            file_path = os.path.join(DOCS_DIR, safe_name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
        st.success(f"{len(uploaded_files)} file(s) uploaded")
        if st.button("Index Uploaded Files", use_container_width=True):
            with st.spinner("Indexing..."):
                ingest_all()
                st.session_state.ingested = True
            st.success("Files indexed!")

    st.divider()

    # New conversation
    if st.button("➕ New Conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    # Past sessions
    st.subheader("Past Conversations")
    sessions = get_all_sessions()
    for session_id, title, last_active in sessions:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                f"💬 {title[:30]}",
                key=f"session_{session_id}",
                use_container_width=True
            ):
                st.session_state.session_id = session_id
                messages = get_session_messages(session_id)
                st.session_state.messages = [
                    {"role": role, "content": content,
                     "source": source, "confidence": conf}
                    for role, content, _, source, conf in messages
                ]
                st.rerun()
        with col2:
            if st.button("🗑", key=f"del_{session_id}"):
                delete_session(session_id)
                st.rerun()

# ── Main area ─────────────────────────────────────────────────
st.title("☁️ CloudMind — AWS Intelligence Platform")
st.caption("Ask anything about your AWS infrastructure, costs, and documentation.")

# Knowledge base status
if not st.session_state.ingested:
    st.warning("Knowledge base is empty. Click 'Refresh AWS Data' in sidebar to get started.")
else:
    st.success("Knowledge base ready — ask your question below.")

st.divider()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message["role"] == "assistant":
            source = message.get("source", "")
            confidence = message.get("confidence", 0)
            if source and source != "system":
                st.caption(f"Source: {source} | Confidence: {int(confidence * 100)}%")

# Chat input
if prompt := st.chat_input("Ask about your AWS costs, instances, incidents..."):
    if not st.session_state.ingested:
        st.error("Please refresh AWS data first using the sidebar button.")
    else:
        st.session_state.messages.append({
            "role": "user", "content": prompt,
            "source": "", "confidence": 0
        })
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            result = None
            with st.spinner("Thinking..."):
                try:
                    result = run_pipeline(prompt, st.session_state.session_id)
                except Exception:
                    logger.exception("run_pipeline failed")
                    st.error("Something went wrong, please try again.")

            if result is not None:
                answer = result["answer"]
                confidence = result["confidence"]
                source = result["source"]

                st.write(answer)
                if source and source != "system":
                    st.caption(
                        f"Source: {source} | "
                        f"Confidence: {int(confidence * 100)}%"
                    )

        if result is not None:
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "source": source,
                "confidence": confidence
            })