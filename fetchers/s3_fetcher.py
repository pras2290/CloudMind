import boto3
import os
from datetime import datetime, timezone
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

def fetch_s3_buckets():
    """Fetch all S3 buckets and their details."""
    client = get_boto3_client("s3")
    response = client.list_buckets()

    docs = []
    for bucket in response["Buckets"]:
        bucket_name = bucket["Name"]
        created = bucket["CreationDate"].strftime("%Y-%m-%d")

        # Get bucket location
        try:
            location = client.get_bucket_location(Bucket=bucket_name)
            region = location["LocationConstraint"] or "us-east-1"
        except:
            region = "unknown"

        # Get bucket size and object count
        try:
            cw = get_boto3_client("cloudwatch")
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
        except:
            size_mb = "unknown"

        # Get versioning status
        try:
            versioning = client.get_bucket_versioning(Bucket=bucket_name)
            versioning_status = versioning.get("Status", "Disabled")
        except:
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
    client = get_boto3_client("s3")
    response = client.list_buckets()

    docs = []
    for bucket in response["Buckets"]:
        bucket_name = bucket["Name"]
        try:
            policy = client.get_bucket_policy(Bucket=bucket_name)
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
        except:
            # No policy attached
            pass
    return docs


def fetch_all_s3_data():
    """Fetch all S3 related data."""
    docs = []
    print("Fetching S3 buckets...")
    docs.extend(fetch_s3_buckets())
    print("Fetching S3 bucket policies...")
    docs.extend(fetch_s3_bucket_policies())
    print(f"S3 fetcher done — {len(docs)} documents")
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = fetch_all_s3_data()
    print(f"\nTotal docs: {len(docs)}")
    print("\nSample:")
    for doc in docs[:3]:
        print(f"\n{doc.page_content}")
        print(f"Metadata: {doc.metadata}")