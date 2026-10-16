import logging
from datetime import datetime, timezone, timedelta
from langchain_core.documents import Document
from fetchers.common import (
    AWS_ERRORS, get_boto3_client, paginate, record_fetch_failure
)

logger = logging.getLogger(__name__)


def fetch_lambda_functions():
    """Fetch all Lambda functions and their details."""
    docs = []
    try:
        client = get_boto3_client("lambda")
        functions = paginate(client, "list_functions", "Functions")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_lambda", "functions", e)
        return docs

    for fn in functions:
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
    docs = []
    try:
        lambda_client = get_boto3_client("lambda")
        cw_client = get_boto3_client("cloudwatch")
        functions = paginate(lambda_client, "list_functions", "Functions")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_lambda", "functions (metrics)", e)
        return docs

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    for fn in functions:
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
        except AWS_ERRORS as e:
            record_fetch_failure("aws_lambda", f"metrics for {fn_name}", e)
            continue

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

    return docs


def fetch_all_lambda_data():
    """Fetch all Lambda related data."""
    docs = []
    logger.info("Fetching Lambda functions...")
    docs.extend(fetch_lambda_functions())
    logger.info("Fetching Lambda metrics...")
    docs.extend(fetch_lambda_metrics())
    logger.info("Lambda fetcher done — %d documents", len(docs))
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    docs = fetch_all_lambda_data()
    logger.info("\nTotal docs: %d", len(docs))
    logger.info("\nSample:")
    for doc in docs[:3]:
        logger.info("\n%s", doc.page_content)
        logger.info("Metadata: %s", doc.metadata)
