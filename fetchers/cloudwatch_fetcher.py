import logging
from datetime import datetime
from langchain_core.documents import Document
from fetchers.common import (
    AWS_ERRORS, get_boto3_client, paginate, record_fetch_failure
)

logger = logging.getLogger(__name__)


def fetch_cloudwatch_alarms():
    """Fetch all CloudWatch alarms and their states."""
    docs = []
    try:
        client = get_boto3_client("cloudwatch")
        alarms = paginate(client, "describe_alarms", "MetricAlarms")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_cloudwatch", "alarms", e)
        return docs

    for alarm in alarms:
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
    docs = []
    try:
        client = get_boto3_client("logs")
        log_groups = paginate(client, "describe_log_groups", "logGroups")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_cloudwatch", "log groups", e)
        return docs

    for lg in log_groups:
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
    docs = []
    try:
        client = get_boto3_client("cloudwatch")
        alarms = paginate(
            client, "describe_alarms", "MetricAlarms",
            AlarmNamePrefix="Billing"
        )
    except AWS_ERRORS as e:
        record_fetch_failure("aws_cloudwatch", "billing alarms", e)
        return docs

    if alarms:
        for alarm in alarms:
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
    logger.info("Fetching CloudWatch alarms...")
    docs.extend(fetch_cloudwatch_alarms())
    logger.info("Fetching CloudWatch log groups...")
    docs.extend(fetch_cloudwatch_log_groups())
    logger.info("Fetching billing alarms...")
    docs.extend(fetch_billing_alarm())
    logger.info("CloudWatch fetcher done — %d documents", len(docs))
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    docs = fetch_all_cloudwatch_data()
    logger.info("\nTotal docs: %d", len(docs))
    logger.info("\nSample:")
    for doc in docs[:3]:
        logger.info("\n%s", doc.page_content)
        logger.info("Metadata: %s", doc.metadata)
