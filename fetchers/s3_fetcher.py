import logging
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from langchain_core.documents import Document
from fetchers.common import AWS_ERRORS, get_boto3_client, record_fetch_failure

logger = logging.getLogger(__name__)


def _list_buckets(client):
    return client.list_buckets()["Buckets"]


def fetch_s3_buckets():
    """Fetch all S3 buckets and their details."""
    docs = []
    try:
        client = get_boto3_client("s3")
        buckets = _list_buckets(client)
    except AWS_ERRORS as e:
        record_fetch_failure("aws_s3", "buckets", e)
        return docs

    try:
        cw = get_boto3_client("cloudwatch")
    except AWS_ERRORS as e:
        logger.warning("CloudWatch client unavailable for S3 sizes: %s", e)
        cw = None

    for bucket in buckets:
        bucket_name = bucket["Name"]
        created = bucket["CreationDate"].strftime("%Y-%m-%d")

        # Get bucket location
        try:
            location = client.get_bucket_location(Bucket=bucket_name)
            region = location["LocationConstraint"] or "us-east-1"
        except Exception as e:
            logger.warning("S3 location lookup failed for %s: %s", bucket_name, e)
            region = "unknown"

        # Get bucket size and object count
        try:
            if cw is None:
                raise RuntimeError("no CloudWatch client")
            size_response = cw.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "StorageType", "Value": "StandardStorage"}
                ],
                StartTime=datetime.now(timezone.utc).replace(hour=0),
                EndTime=datetime.now(timezone.utc),
                Period=86400,
                Statistics=["Average"]
            )
            size = size_response["Datapoints"][0]["Average"] if size_response["Datapoints"] else 0
            size_mb = round(size / (1024 * 1024), 2)
        except Exception as e:
            logger.warning("S3 size lookup failed for %s: %s", bucket_name, e)
            size_mb = "unknown"

        # Get versioning status
        try:
            versioning = client.get_bucket_versioning(Bucket=bucket_name)
            versioning_status = versioning.get("Status", "Disabled")
        except Exception as e:
            logger.warning("S3 versioning lookup failed for %s: %s", bucket_name, e)
            versioning_status = "unknown"

        text = f"""S3 Bucket Details:
Name: {bucket_name}
Created: {created}
Region: {region}
Size: {size_mb} MB
Versioning: {versioning_status}"""

        docs.append(Document(
            page_content=text,
            metadata={
                "source": "aws_s3",
                "bucket": bucket_name,
                "region": region,
                "type": "s3_bucket"
            }
        ))
    return docs


def fetch_s3_bucket_policies():
    """Fetch bucket policies for all buckets."""
    docs = []
    try:
        client = get_boto3_client("s3")
        buckets = _list_buckets(client)
    except AWS_ERRORS as e:
        record_fetch_failure("aws_s3", "buckets (policies)", e)
        return docs

    for bucket in buckets:
        bucket_name = bucket["Name"]
        try:
            policy = client.get_bucket_policy(Bucket=bucket_name)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchBucketPolicy":
                continue  # No policy attached
            record_fetch_failure("aws_s3", f"policy for {bucket_name}", e)
            continue
        except AWS_ERRORS as e:
            record_fetch_failure("aws_s3", f"policy for {bucket_name}", e)
            continue

        text = f"""S3 Bucket Policy:
Bucket: {bucket_name}
Policy: {policy['Policy']}"""
        docs.append(Document(
            page_content=text,
            metadata={
                "source": "aws_s3",
                "bucket": bucket_name,
                "type": "s3_policy"
            }
        ))
    return docs


def fetch_all_s3_data():
    """Fetch all S3 related data."""
    docs = []
    logger.info("Fetching S3 buckets...")
    docs.extend(fetch_s3_buckets())
    logger.info("Fetching S3 bucket policies...")
    docs.extend(fetch_s3_bucket_policies())
    logger.info("S3 fetcher done — %d documents", len(docs))
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    docs = fetch_all_s3_data()
    logger.info("\nTotal docs: %d", len(docs))
    logger.info("\nSample:")
    for doc in docs[:3]:
        logger.info("\n%s", doc.page_content)
        logger.info("Metadata: %s", doc.metadata)
