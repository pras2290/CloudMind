import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.retriever import retrieve, load_vectorstore, get_embeddings
from rag.memory import (
    init_db, create_session, save_message,
    get_chat_history, update_session_title
)
from config import (
    OPENAI_API_KEY, LLM_MODEL, TEMPERATURE,
    CHROMA_DB_PATH, COLLECTION_NAME, CONFIDENCE_THRESHOLD, TOP_K
)


def get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        api_key=OPENAI_API_KEY
    )


def load_all_docs():
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
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


def fallback_response(query, llm):
    import boto3
    from dotenv import load_dotenv
    load_dotenv()

    try:
        if any(w in query.lower() for w in ["instance", "ec2", "running", "stopped"]):
            client = boto3.client(
                "ec2",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION")
            )
            response = client.describe_instances()
            instances = []
            for r in response["Reservations"]:
                for i in r["Instances"]:
                    name = next((t["Value"] for t in i.get("Tags", [])
                                 if t["Key"] == "Name"), "unnamed")
                    instances.append(
                        f"Name: {name} | ID: {i['InstanceId']} | "
                        f"Type: {i['InstanceType']} | State: {i['State']['Name']}"
                    )
            context = "Live EC2 Data:\n" + "\n".join(instances) if instances else "No EC2 instances found."
            return context, "live_aws_ec2"

        elif any(w in query.lower() for w in ["cost", "bill", "spend"]):
            from datetime import datetime, timedelta
            client = boto3.client(
                "ce",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name="us-east-1"
            )
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

    except Exception as e:
        print(f"Fallback error: {e}")

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
    print(f"Rewritten: {rewritten_query}")

    # Detect source filter
    source_filter = detect_source_filter(query)
    print(f"Source filter: {source_filter}")

    # Retrieve
    if is_live_query(query):
        print("Live query — boto3 fallback")
        context, source = fallback_response(query, llm)
        confidence = 0.9
        docs = []
    elif source_filter:
        # Targeted metadata filtered search
        print(f"Targeted search with filter: {source_filter}")
        docs = vectorstore.similarity_search(
            rewritten_query,
            k=TOP_K,
            filter=source_filter
        )
        confidence = 0.85 if docs else 0.0
        context = format_docs(docs) if docs else ""
    elif is_broad_query(query):
        # Fetch from all sources
        print("Broad query — fetching from all sources")
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
        docs, confidence = retrieve(rewritten_query, vectorstore, all_docs)
        context = format_docs(docs) if docs else ""

    # Fallback if no context
    if not context or confidence < CONFIDENCE_THRESHOLD:
        print("Low confidence — fallback")
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
    session_id = str(uuid.uuid4())
    query = "How many S3 buckets do I have?"
    print(f"Query: {query}\n")
    result = run_pipeline(query, session_id)
    print(f"\nAnswer: {result['answer']}")
    print(f"Confidence: {result['confidence']:.4f}")
    print(f"Source: {result['source']}")