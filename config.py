import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# AWS
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Paths
CHROMA_DB_PATH = "./chroma_db"
SQLITE_DB_PATH = "./memory.db"
UPLOAD_PATH = "./uploads"
DATA_PATH = "./data"

# Collection
COLLECTION_NAME = "cloudmind_docs"

# Embedding
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

# LLM
LLM_MODEL = "gpt-4o-mini"
TEMPERATURE = 0

# Retrieval
TOP_K = 8
CONFIDENCE_THRESHOLD = 0.3
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200