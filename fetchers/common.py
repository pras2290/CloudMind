"""Shared AWS client, model, vectorstore helpers and core constants."""
import functools
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
CHROMA_DIR = "./chroma_db"
DOCS_DIR = "./uploads"
COLLECTION_NAME = "cloudmind_docs"
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_K = 8
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Errors raised by boto3 for API failures (ClientError) and for
# client-side problems such as missing credentials/region (BotoCoreError).
AWS_ERRORS = (ClientError, BotoCoreError)


# ── AWS ───────────────────────────────────────────────────────
def get_boto3_client(service, region_name=None):
    """Create a boto3 client.

    Explicit keys from the environment are used when both are set; otherwise
    boto3's default credential chain (IAM role, SSO, ~/.aws, ...) applies.
    """
    kwargs = {"region_name": region_name or os.getenv("AWS_REGION")}
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client(service, **kwargs)


def paginate(client, operation, result_key, **kwargs):
    """Return every item of `result_key` across all pages of `operation`."""
    items = []
    for page in client.get_paginator(operation).paginate(**kwargs):
        items.extend(page.get(result_key, []))
    return items


# Sources whose AWS fetch hit an error during the current run. Ingestion uses
# this to avoid pruning previously indexed docs for services that failed.
_fetch_failures = set()


def record_fetch_failure(source, what, exc):
    _fetch_failures.add(source)
    logger.warning("%s: failed to fetch %s: %s", source, what, exc)


def reset_fetch_failures():
    _fetch_failures.clear()


def get_fetch_failures():
    return set(_fetch_failures)


# ── Models ────────────────────────────────────────────────────
@functools.lru_cache(maxsize=1)
def get_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True}
    )


@functools.lru_cache(maxsize=1)
def get_reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(RERANKER_MODEL)


# ── Vectorstore ───────────────────────────────────────────────
def load_vectorstore():
    """Load (or create) the persistent ChromaDB vectorstore."""
    from langchain_chroma import Chroma

    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=get_embeddings(),
        collection_name=COLLECTION_NAME
    )


def vectorstore_exists():
    """Check if ChromaDB already has data."""
    return os.path.exists(CHROMA_DIR) and \
           len(os.listdir(CHROMA_DIR)) > 0
