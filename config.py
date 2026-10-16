import os
from dotenv import load_dotenv
from fetchers.common import (  # noqa: F401 (re-exported)
    CHROMA_DIR, DOCS_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    TOP_K, CHUNK_SIZE, CHUNK_OVERLAP
)

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# AWS
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Paths
CHROMA_DB_PATH = CHROMA_DIR
SQLITE_DB_PATH = "./memory.db"
UPLOAD_PATH = DOCS_DIR
DATA_PATH = "./data"

# LLM
LLM_MODEL = "gpt-4o-mini"
TEMPERATURE = 0

# Retrieval
CONFIDENCE_THRESHOLD = 0.3
