import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from config import (
    CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL, TOP_K
)


# ── Load embeddings ───────────────────────────────────────────
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True}
    )


# ── Load vectorstore ──────────────────────────────────────────
def load_vectorstore():
    embeddings = get_embeddings()
    return Chroma(
        persist_directory=CHROMA_DB_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )


# ── Reranker ──────────────────────────────────────────────────
def get_reranker():
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def rerank(query, docs, reranker, top_n=3):
    """Rerank retrieved docs using CrossEncoder."""
    if not docs:
        return []
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, docs), reverse=True)
    return [doc for _, doc in ranked[:top_n]]


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
    """Get similarity score of top result."""
    if not docs:
        return 0.0
    query_embedding = embeddings.embed_query(query)
    doc_embedding = embeddings.embed_documents([docs[0].page_content])[0]

    # Cosine similarity
    dot = sum(a * b for a, b in zip(query_embedding, doc_embedding))
    norm_q = sum(a ** 2 for a in query_embedding) ** 0.5
    norm_d = sum(b ** 2 for b in doc_embedding) ** 0.5
    return dot / (norm_q * norm_d) if norm_q and norm_d else 0.0


# ── Main retrieve function ────────────────────────────────────
def retrieve(query, vectorstore, all_docs):
    """Full retrieval pipeline — hybrid search + reranking."""
    embeddings = get_embeddings()
    reranker = get_reranker()

    # Hybrid retrieval
    retriever = get_hybrid_retriever(vectorstore, all_docs)
    docs = retriever.invoke(query)

    # Confidence score
    confidence = get_confidence_score(query, docs, embeddings)

    # Rerank
    reranked_docs = rerank(query, docs, reranker)

    return reranked_docs, confidence


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    from rag.ingestion import load_vectorstore, ingest_all
    import chromadb

    print("Loading vectorstore...")
    vectorstore = load_vectorstore()

    # Load all docs for BM25
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_collection(COLLECTION_NAME)
    results = collection.get()
    all_docs = [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(results["documents"], results["metadatas"])
    ]

    print(f"Loaded {len(all_docs)} docs for BM25")

    query = "What is my AWS cost for last month?"
    print(f"\nQuery: {query}")

    docs, confidence = retrieve(query, vectorstore, all_docs)

    print(f"Confidence: {confidence:.4f}")
    print(f"Top {len(docs)} results:")
    for i, doc in enumerate(docs):
        print(f"\n--- Result {i+1} ---")
        print(doc.page_content[:300])
        print(f"Source: {doc.metadata.get('source', 'N/A')}")