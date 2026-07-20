import boto3
import os
from datetime import datetime, timezone, timedelta
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

def get_boto3_client(service):
    return boto3.client(
        service,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )

def fetch_lambda_functions():
    """Fetch all Lambda functions and their details."""
    client = get_boto3_client("lambda")
    
    docs = []
    paginator = client.get_paginator("list_functions")
    
    for page in paginator.paginate():
        for fn in page["Functions"]:
            text = f"""Lambda Function Details:
Name: {fn['FunctionName']}
Runtime: {fn.get('Runtime', 'N/A')}
Handler: {fn.get('Handler', 'N/A')}
Memory: {fn.get('MemorySize', 'N/A')} MB
Timeout: {fn.get('Timeout', 'N/A')} seconds
Last Modified: {fn.get('LastModified', 'N/A')}
Description: {fn.get('Description', 'No description')}
Code Size: {fn.get('CodeSize', 'N/A')} bytes
ARN: {fn.get('FunctionArn', 'N/A')}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_lambda",
                    "function_name": fn["FunctionName"],
                    "runtime": fn.get("Runtime", "N/A"),
                    "type": "lambda_function"
                }
            ))
    return docs


def fetch_lambda_metrics():
    """Fetch Lambda invocation and error metrics for last 7 days."""
    lambda_client = get_boto3_client("lambda")
    cw_client = get_boto3_client("cloudwatch")

    paginator = lambda_client.get_paginator("list_functions")
    docs = []

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    for page in paginator.paginate():
        for fn in page["Functions"]:
            fn_name = fn["FunctionName"]

            try:
                # Invocations
                inv = cw_client.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Invocations",
                    Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=604800,
                    Statistics=["Sum"]
                )
                invocations = inv["Datapoints"][0]["Sum"] if inv["Datapoints"] else 0

                # Errors
                err = cw_client.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Errors",
                    Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=604800,
                    Statistics=["Sum"]
                )
                errors = err["Datapoints"][0]["Sum"] if err["Datapoints"] else 0

                text = f"""Lambda Metrics (Last 7 days):
Function: {fn_name}
Invocations: {invocations}
Errors: {errors}
Error Rate: {round((errors/invocations)*100, 2) if invocations > 0 else 0}%"""

                docs.append(Document(
                    page_content=text,
                    metadata={
                        "source": "aws_lambda",
                        "function_name": fn_name,
                        "type": "lambda_metrics"
                    }
                ))
            except Exception as e:
                print(f"Metrics error for {fn_name}: {e}")

    return docs


def fetch_all_lambda_data():
    """Fetch all Lambda related data."""
    docs = []
    print("Fetching Lambda functions...")
    docs.extend(fetch_lambda_functions())
    print("Fetching Lambda metrics...")
    docs.extend(fetch_lambda_metrics())
    print(f"Lambda fetcher done — {len(docs)} documents")
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = fetch_all_lambda_data()
    print(f"\nTotal docs: {len(docs)}")
    print("\nSample:")
    for doc in docs[:3]:
        print(f"\n{doc.page_content}")
        print(f"Metadata: {doc.metadata}")