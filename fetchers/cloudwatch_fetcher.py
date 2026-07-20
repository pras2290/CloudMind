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

def fetch_cloudwatch_alarms():
    """Fetch all CloudWatch alarms and their states."""
    client = get_boto3_client("cloudwatch")
    paginator = client.get_paginator("describe_alarms")

    docs = []
    for page in paginator.paginate():
        for alarm in page["MetricAlarms"]:
            text = f"""CloudWatch Alarm:
Name: {alarm['AlarmName']}
State: {alarm['StateValue']}
Description: {alarm.get('AlarmDescription', 'No description')}
Metric: {alarm.get('MetricName', 'N/A')}
Namespace: {alarm.get('Namespace', 'N/A')}
Threshold: {alarm.get('Threshold', 'N/A')}
Comparison: {alarm.get('ComparisonOperator', 'N/A')}
Last Updated: {alarm.get('StateUpdatedTimestamp', 'N/A')}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_cloudwatch",
                    "alarm_name": alarm["AlarmName"],
                    "state": alarm["StateValue"],
                    "type": "cloudwatch_alarm"
                }
            ))
    return docs


def fetch_cloudwatch_log_groups():
    """Fetch all CloudWatch log groups."""
    client = get_boto3_client("logs")
    paginator = client.get_paginator("describe_log_groups")

    docs = []
    for page in paginator.paginate():
        for lg in page["logGroups"]:
            size_mb = round(lg.get("storedBytes", 0) / (1024 * 1024), 2)
            text = f"""CloudWatch Log Group:
Name: {lg['logGroupName']}
Stored Size: {size_mb} MB
Retention: {lg.get('retentionInDays', 'Never expire')} days
Created: {datetime.fromtimestamp(lg.get('creationTime', 0)/1000).strftime('%Y-%m-%d')}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_cloudwatch",
                    "log_group": lg["logGroupName"],
                    "type": "log_group"
                }
            ))
    return docs


def fetch_billing_alarm():
    """Check if billing alarm is configured."""
    client = get_boto3_client("cloudwatch")

    response = client.describe_alarms(
        AlarmNamePrefix="Billing"
    )

    docs = []
    if response["MetricAlarms"]:
        for alarm in response["MetricAlarms"]:
            text = f"""Billing Alarm:
Name: {alarm['AlarmName']}
State: {alarm['StateValue']}
Threshold: ${alarm.get('Threshold', 'N/A')}
Description: {alarm.get('AlarmDescription', 'No description')}"""
            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_cloudwatch",
                    "type": "billing_alarm"
                }
            ))
    else:
        docs.append(Document(
            page_content="No billing alarms configured in this AWS account.",
            metadata={"source": "aws_cloudwatch", "type": "billing_alarm"}
        ))
    return docs


def fetch_all_cloudwatch_data():
    """Fetch all CloudWatch related data."""
    docs = []
    print("Fetching CloudWatch alarms...")
    docs.extend(fetch_cloudwatch_alarms())
    print("Fetching CloudWatch log groups...")
    docs.extend(fetch_cloudwatch_log_groups())
    print("Fetching billing alarms...")
    docs.extend(fetch_billing_alarm())
    print(f"CloudWatch fetcher done — {len(docs)} documents")
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = fetch_all_cloudwatch_data()
    print(f"\nTotal docs: {len(docs)}")
    print("\nSample:")
    for doc in docs[:3]:
        print(f"\n{doc.page_content}")
        print(f"Metadata: {doc.metadata}")