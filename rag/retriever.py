import logging
import math

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from fetchers.common import (  # noqa: F401 (re-exported)
    CHROMA_DIR, COLLECTION_NAME, TOP_K,
    get_embeddings, get_reranker, load_vectorstore
)

logger = logging.getLogger(__name__)


def _rerank_with_scores(query, docs, reranker, top_n=3):
    """Return [(score, doc), ...] sorted by CrossEncoder score, best first."""
    if not docs:
        return []
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, docs), key=lambda pair: pair[0], reverse=True)
    return ranked[:top_n]


def rerank(query, docs, reranker, top_n=3):
    """Rerank retrieved docs using CrossEncoder."""
    return [doc for _, doc in _rerank_with_scores(query, docs, reranker, top_n)]


# ── Hybrid retriever ──────────────────────────────────────────
def get_hybrid_retriever(vectorstore, all_docs):
    """Combine BM25 sparse + ChromaDB dense retrieval."""

    # Dense retriever
    dense_retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": TOP_K, "fetch_k": 30}
    )

    # Sparse BM25 retriever
    bm25_retriever = BM25Retriever.from_documents(all_docs)
    bm25_retriever.k = TOP_K

    # Ensemble — 50% dense + 50% sparse
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, dense_retriever],
        weights=[0.5, 0.5]
    )

    return ensemble_retriever


# ── Confidence check ──────────────────────────────────────────
def get_confidence_score(query, docs, embeddings):
    """Cosine similarity of query vs top doc (legacy confidence metric)."""
    if not docs:
        return 0.0
    query_embedding = embeddings.embed_query(query)
    doc_embedding = embeddings.embed_documents([docs[0].page_content])[0]

    # Cosine similarity
    dot = sum(a * b for a, b in zip(query_embedding, doc_embedding))
    norm_q = sum(a ** 2 for a in query_embedding) ** 0.5
    norm_d = sum(b ** 2 for b in doc_embedding) ** 0.5
    return dot / (norm_q * norm_d) if norm_q and norm_d else 0.0


def reranker_confidence(score):
    """Map a CrossEncoder logit to a 0-1 confidence."""
    return 1.0 / (1.0 + math.exp(-float(score)))


# ── Main retrieve function ────────────────────────────────────
def retrieve(query, vectorstore, all_docs):
    """Full retrieval pipeline — hybrid search + reranking."""
    reranker = get_reranker()

    # Hybrid retrieval
    retriever = get_hybrid_retriever(vectorstore, all_docs)
    docs = retriever.invoke(query)

    # Rerank; confidence is the top reranked doc's score
    ranked = _rerank_with_scores(query, docs, reranker)
    reranked_docs = [doc for _, doc in ranked]
    confidence = reranker_confidence(ranked[0][0]) if ranked else 0.0

    return reranked_docs, confidence


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import chromadb

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Loading vectorstore...")
    vectorstore = load_vectorstore()

    # Load all docs for BM25
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_collection(COLLECTION_NAME)
    results = collection.get()
    all_docs = [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(results["documents"], results["metadatas"])
    ]

    logger.info("Loaded %d docs for BM25", len(all_docs))

    query = "What is my AWS cost for last month?"
    logger.info("\nQuery: %s", query)

    docs, confidence = retrieve(query, vectorstore, all_docs)

    logger.info("Confidence: %.4f", confidence)
    logger.info("Top %d results:", len(docs))
    for i, doc in enumerate(docs):
        logger.info("\n--- Result %d ---", i + 1)
        logger.info(doc.page_content[:300])
        logger.info("Source: %s", doc.metadata.get('source', 'N/A'))
