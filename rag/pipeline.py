import logging
from datetime import datetime, timedelta

import chromadb
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.retriever import (  # noqa: F401 (retrieve re-exported)
    retrieve, retrieve_with_scores, load_vectorstore, get_embeddings
)
from rag.memory import (
    init_db, create_session, save_message,
    get_chat_history, update_session_title
)
from fetchers.common import (
    CHROMA_DIR, COLLECTION_NAME, TOP_K, get_boto3_client, paginate
)
from config import (
    OPENAI_API_KEY, LLM_MODEL, TEMPERATURE, CONFIDENCE_THRESHOLD
)

logger = logging.getLogger(__name__)


def get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        api_key=OPENAI_API_KEY
    )


def load_all_docs():
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_collection(COLLECTION_NAME)
    results = collection.get()
    return [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(results["documents"], results["metadatas"])
    ]


def detect_source_filter(query):
    """Route query to correct AWS source using metadata."""
    q = query.lower()
    if any(w in q for w in ["s3", "bucket", "storage", "object"]):
        return {"source": "aws_s3"}
    elif any(w in q for w in ["ec2", "instance", "server", "virtual machine", "vpc", "security group"]):
        return {"source": "aws_ec2"}
    elif any(w in q for w in ["lambda", "function", "serverless", "invocation"]):
        return {"source": "aws_lambda"}
    elif any(w in q for w in ["cost", "bill", "spend", "charge", "pricing", "expense"]):
        return {"source": "aws_cost_explorer"}
    elif any(w in q for w in ["alarm", "cloudwatch", "metric", "log", "monitoring"]):
        return {"source": "aws_cloudwatch"}
    elif any(w in q for w in ["iam", "user", "role", "policy", "permission", "mfa", "access"]):
        return {"source": "aws_iam"}
    elif any(w in q for w in ["runbook", "sop", "procedure", "how to", "troubleshoot"]):
        return {"type": "pdf"}
    elif any(w in q for w in ["error", "kedb", "known error", "incident"]):
        return {"type": "pdf"}
    return None


def is_broad_query(query):
    broad = ["all resources", "everything", "list all",
             "what do i have", "all services", "overview",
             "summarize", "what services", "resources in",
             "resources i have", "my resources"]
    return any(k in query.lower() for k in broad)


def is_live_query(query):
    live = ["right now", "currently", "at this moment",
            "live", "running now", "latest", "current"]
    return any(k in query.lower() for k in live)


def is_aws_related(query):
    aws_keywords = [
        "aws", "ec2", "s3", "lambda", "cloudwatch", "iam", "cost",
        "bill", "instance", "bucket", "function", "alarm", "role",
        "policy", "vpc", "subnet", "security group", "rds", "dynamo",
        "runbook", "incident", "error", "kedb", "sop", "cloud",
        "resource", "server", "storage", "compute"
    ]
    return any(k in query.lower() for k in aws_keywords)


def rewrite_query(query, llm):
    if not is_aws_related(query):
        return query
    prompt = f"""Rewrite this AWS question to improve search accuracy.
Be specific. Return only the rewritten question, nothing else.
Original: {query}
Rewritten:"""
    response = llm.invoke(prompt)
    return response.content.strip()


def build_prompt():
    return ChatPromptTemplate.from_template("""
You are CloudMind — an intelligent AWS Intelligence Assistant.

IMPORTANT RULES:
1. The context below contains REAL data from the user's AWS account.
2. Use ALL information in context to answer completely.
3. If context has the answer — use it directly and confidently.
4. Never say "I don't have information" if data is visible in context.
5. For listing resources — list EVERY item mentioned in context.
6. Present data in tables when user asks for lists.
7. Be specific, technical, and direct.

Context:
{context}

Chat History:
{chat_history}

Question:
{question}

Answer:
""")


def format_docs(docs):
    formatted = []
    for i, doc in enumerate(docs):
        source = doc.metadata.get("source", "unknown")
        formatted.append(f"[{i+1}] Source: {source}\n{doc.page_content}")
    return "\n\n".join(formatted)


def _live_ec2_context():
    client = get_boto3_client("ec2")
    instances = []
    for r in paginate(client, "describe_instances", "Reservations"):
        for i in r["Instances"]:
            name = next((t["Value"] for t in i.get("Tags", [])
                         if t["Key"] == "Name"), "unnamed")
            instances.append(
                f"Name: {name} | ID: {i['InstanceId']} | "
                f"Type: {i['InstanceType']} | State: {i['State']['Name']}"
            )
    context = "Live EC2 Data:\n" + "\n".join(instances) if instances else "No EC2 instances found."
    return context, "live_aws_ec2"


def _live_cost_context():
    client = get_boto3_client("ce", region_name="us-east-1")
    end = datetime.today().replace(day=1).strftime("%Y-%m-%d")
    start = (datetime.today().replace(day=1) -
             timedelta(days=30)).strftime("%Y-%m-%d")
    response = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"]
    )
    cost = response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
    context = f"Live AWS Cost: Total last month = ${round(float(cost), 4)} USD"
    return context, "live_aws_cost"


def fetch_live_context(query):
    """Fetch live EC2/Cost data straight from AWS for the query, or None."""
    q = query.lower()
    if any(w in q for w in ["instance", "ec2", "running", "stopped"]):
        return _live_ec2_context()
    elif any(w in q for w in ["cost", "bill", "spend"]):
        return _live_cost_context()
    return None


def fallback_response(query, llm):
    try:
        live = fetch_live_context(query)
        if live is not None:
            return live
    except Exception:
        logger.exception("Fallback error")

    return "No relevant information found.", "none"


def run_pipeline(query, session_id):
    init_db()
    create_session(session_id)

    llm = get_llm()
    vectorstore = load_vectorstore()
    all_docs = load_all_docs()

    # Chat history
    chat_history = get_chat_history(session_id)
    history_text = "\n".join(
        [f"{m['role'].upper()}: {m['content']}" for m in chat_history]
    ) if chat_history else "No previous conversation."

    # General responses
    general_responses = {
        "your name": "I am CloudMind — your AWS Intelligence Assistant.",
        "who are you": "I am CloudMind — your AWS Intelligence Assistant.",
        "what are you": "I am CloudMind — an AI-powered RAG assistant for AWS intelligence.",
        "what can you do": """I can answer questions about:
- AWS costs and billing
- EC2 instances, VPCs, security groups
- S3 buckets
- Lambda functions and metrics
- CloudWatch alarms and logs
- IAM users, roles, and policies
- Runbooks, SOPs, and KEDB documents""",
        "what data": """I have access to:
- Your live AWS account data (EC2, S3, Lambda, IAM, CloudWatch, Cost Explorer)
- Uploaded documents (Runbooks, SOPs, KEDB)""",
    }

    for key, response in general_responses.items():
        if key in query.lower():
            save_message(session_id, "user", query)
            save_message(session_id, "assistant", response)
            return {
                "answer": response,
                "confidence": 1.0,
                "source": "system",
                "rewritten_query": query,
                "docs": []
            }

    # Rewrite query
    rewritten_query = rewrite_query(query, llm)
    logger.info("Rewritten: %s", rewritten_query)

    # Detect source filter
    source_filter = detect_source_filter(query)
    logger.info("Source filter: %s", source_filter)

    # Retrieve
    routing_confidence = None
    if is_live_query(query):
        logger.info("Live query — boto3 fallback")
        context, source = fallback_response(query, llm)
        confidence = 0.9
        docs = []
    elif source_filter:
        # Targeted metadata filtered search
        logger.info("Targeted search with filter: %s", source_filter)
        docs = vectorstore.similarity_search(
            rewritten_query,
            k=TOP_K,
            filter=source_filter
        )
        confidence = 0.85 if docs else 0.0
        context = format_docs(docs) if docs else ""
    elif is_broad_query(query):
        # Fetch from all sources
        logger.info("Broad query — fetching from all sources")
        docs = []
        for src in ["aws_s3", "aws_ec2", "aws_lambda",
                    "aws_cloudwatch", "aws_iam", "aws_cost_explorer"]:
            results = vectorstore.similarity_search(
                rewritten_query,
                k=2,
                filter={"source": src}
            )
            docs.extend(results)
        confidence = 0.85 if docs else 0.0
        context = format_docs(docs) if docs else ""
    else:
        # Hybrid search
        docs, confidence, routing_confidence = retrieve_with_scores(
            rewritten_query, vectorstore, all_docs
        )
        context = format_docs(docs) if docs else ""

    # Fallback if no context
    if routing_confidence is None:
        routing_confidence = confidence
    if not context or routing_confidence < CONFIDENCE_THRESHOLD:
        logger.info("Low confidence — fallback")
        context, source = fallback_response(query, llm)
        source = source
    else:
        source = source_filter.get("source", "knowledge_base") if source_filter else "knowledge_base"

    # Generate answer
    prompt = build_prompt()
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "chat_history": history_text,
        "context": context,
        "question": query
    })

    # Save memory
    save_message(session_id, "user", query)
    save_message(session_id, "assistant", answer,
                 source=source, confidence=confidence)

    if len(chat_history) == 0:
        update_session_title(session_id, query)

    return {
        "answer": answer,
        "confidence": confidence,
        "source": source,
        "rewritten_query": rewritten_query,
        "docs": docs
    }


if __name__ == "__main__":
    import uuid
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    session_id = str(uuid.uuid4())
    query = "How many S3 buckets do I have?"
    logger.info("Query: %s\n", query)
    result = run_pipeline(query, session_id)
    logger.info("\nAnswer: %s", result['answer'])
    logger.info("Confidence: %.4f", result['confidence'])
    logger.info("Source: %s", result['source'])