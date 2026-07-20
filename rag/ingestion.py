import os
import pdfplumber
import pandas as pd
import sys
from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from fetchers.cost_fetcher import fetch_all_cost_data
from fetchers.ec2_fetcher import fetch_all_ec2_data
from fetchers.s3_fetcher import fetch_all_s3_data
from fetchers.lambda_fetcher import fetch_all_lambda_data
from fetchers.cloudwatch_fetcher import fetch_all_cloudwatch_data
from fetchers.iam_fetcher import fetch_all_iam_data
from config import (
    CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL,
    CHUNK_SIZE, CHUNK_OVERLAP
)

sys.path.append("/Users/prasannavenkatraman/cloudmind")
# ── Embedding model ───────────────────────────────────────────
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True}
    )


# ── Text splitter ─────────────────────────────────────────────
def get_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )


# ── File loaders ──────────────────────────────────────────────
def load_pdf(file_path):
    docs = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True) or ""
            if text.strip():
                docs.append(Document(
                    page_content=text,
                    metadata={
                        "source": file_path,
                        "page": i + 1,
                        "type": "pdf"
                    }
                ))
    return docs


def load_word(file_path):
    docx = DocxDocument(file_path)
    text = "\n".join([p.text for p in docx.paragraphs if p.text.strip()])
    return [Document(
        page_content=text,
        metadata={"source": file_path, "type": "word"}
    )]


def load_csv(file_path):
    df = pd.read_csv(file_path)
    docs = []
    for i, row in df.iterrows():
        text = "\n".join([f"{col}: {val}" for col, val in row.items()])
        docs.append(Document(
            page_content=text,
            metadata={"source": file_path, "row": i, "type": "csv"}
        ))
    return docs


def load_uploaded_files(upload_path="./uploads"):
    docs = []
    if not os.path.exists(upload_path):
        return docs
    for filename in os.listdir(upload_path):
        file_path = os.path.join(upload_path, filename)
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == ".pdf":
                docs.extend(load_pdf(file_path))
            elif ext == ".docx":
                docs.extend(load_word(file_path))
            elif ext == ".csv":
                docs.extend(load_csv(file_path))
            print(f"Loaded: {filename}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")
    return docs


# ── Master ingestion ──────────────────────────────────────────
def ingest_all():
    all_docs = []
    splitter = get_splitter()

    print("\n── Fetching AWS data ────────────────────")
    all_docs.extend(fetch_all_cost_data())
    all_docs.extend(fetch_all_ec2_data())
    all_docs.extend(fetch_all_s3_data())
    all_docs.extend(fetch_all_lambda_data())
    all_docs.extend(fetch_all_cloudwatch_data())
    all_docs.extend(fetch_all_iam_data())

    print("\n── Loading uploaded files ───────────────")
    all_docs.extend(load_uploaded_files())

    print(f"\nTotal raw documents: {len(all_docs)}")

    # Chunk
    chunks = splitter.split_documents(all_docs)
    print(f"Total chunks after splitting: {len(chunks)}")

    # Embed + Store
    print("\nEmbedding and storing in ChromaDB...")
    embeddings = get_embeddings()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_PATH,
        collection_name=COLLECTION_NAME
    )
    print("Ingestion complete.")
    return vectorstore


def load_vectorstore():
    """Load existing ChromaDB vectorstore."""
    embeddings = get_embeddings()
    return Chroma(
        persist_directory=CHROMA_DB_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )


def vectorstore_exists():
    """Check if ChromaDB already has data."""
    return os.path.exists(CHROMA_DB_PATH) and \
           len(os.listdir(CHROMA_DB_PATH)) > 0


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    # print("Starting full ingestion...")
    # vectorstore = ingest_all()
    # print(f"\nVectorstore ready.")

    # Quick test query
    results = vectorstore.similarity_search("AWS cost", k=3)
    print(f"\nTest query results: {len(results)}")
    for r in results:
        print(f"\n{r.page_content[:200]}")
        print(f"Source: {r.metadata['source']}")