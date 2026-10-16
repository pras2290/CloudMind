import logging
import os
from langchain_core.documents import Document
from fetchers.common import (
    AWS_ERRORS, get_boto3_client, paginate, record_fetch_failure
)

logger = logging.getLogger(__name__)


def fetch_ec2_instances():
    """Fetch all EC2 instances and their details."""
    docs = []
    try:
        client = get_boto3_client("ec2")
        reservations = paginate(client, "describe_instances", "Reservations")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_ec2", "instances", e)
        return docs

    for reservation in reservations:
        for instance in reservation["Instances"]:
            name = ""
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]

            text = f"""EC2 Instance Details:
                    Name: {name}
                    Instance ID: {instance['InstanceId']}
                    Type: {instance['InstanceType']}
                    State: {instance['State']['Name']}
                    Region: {os.getenv('AWS_REGION')}
                    Launch Time: {instance.get('LaunchTime', 'N/A')}
                    Public IP: {instance.get('PublicIpAddress', 'None')}
                    Private IP: {instance.get('PrivateIpAddress', 'None')}
                    AMI ID: {instance.get('ImageId', 'N/A')}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_ec2",
                    "instance_id": instance["InstanceId"],
                    "state": instance["State"]["Name"],
                    "type": "ec2"
                }
            ))
    return docs


def fetch_ec2_security_groups():
    """Fetch all security groups."""
    docs = []
    try:
        client = get_boto3_client("ec2")
        security_groups = paginate(
            client, "describe_security_groups", "SecurityGroups"
        )
    except AWS_ERRORS as e:
        record_fetch_failure("aws_ec2", "security groups", e)
        return docs

    for sg in security_groups:
        inbound = []
        for rule in sg.get("IpPermissions", []):
            protocol = rule.get("IpProtocol", "all")
            port = rule.get("FromPort", "all")
            sources = [ip["CidrIp"] for ip in rule.get("IpRanges", [])]
            inbound.append(f"Protocol: {protocol}, Port: {port}, Sources: {sources}")

        text = f"""Security Group:
                    Name: {sg['GroupName']}
                    ID: {sg['GroupId']}
                    Description: {sg['Description']}
                    VPC ID: {sg.get('VpcId', 'N/A')}
                    Inbound Rules: {'; '.join(inbound) if inbound else 'None'}"""

        docs.append(Document(
            page_content=text,
            metadata={
                "source": "aws_ec2",
                "sg_id": sg["GroupId"],
                "type": "security_group"
            }
        ))
    return docs


def fetch_ec2_vpcs():
    """Fetch all VPCs."""
    docs = []
    try:
        client = get_boto3_client("ec2")
        vpcs = paginate(client, "describe_vpcs", "Vpcs")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_ec2", "VPCs", e)
        return docs

    for vpc in vpcs:
        name = ""
        for tag in vpc.get("Tags", []):
            if tag["Key"] == "Name":
                name = tag["Value"]

        text = f"""VPC Details:
Name: {name}
VPC ID: {vpc['VpcId']}
CIDR Block: {vpc['CidrBlock']}
State: {vpc['State']}
Is Default: {vpc['IsDefault']}"""

        docs.append(Document(
            page_content=text,
            metadata={
                "source": "aws_ec2",
                "vpc_id": vpc["VpcId"],
                "type": "vpc"
            }
        ))
    return docs


def fetch_all_ec2_data():
    """Fetch all EC2 related data."""
    docs = []
    logger.info("Fetching EC2 instances...")
    docs.extend(fetch_ec2_instances())
    logger.info("Fetching security groups...")
    docs.extend(fetch_ec2_security_groups())
    logger.info("Fetching VPCs...")
    docs.extend(fetch_ec2_vpcs())
    logger.info("EC2 fetcher done — %d documents", len(docs))
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    docs = fetch_all_ec2_data()
    logger.info("\nTotal docs: %d", len(docs))
    logger.info("\nSample:")
    for doc in docs[:3]:
        logger.info("\n%s", doc.page_content)
        logger.info("Metadata: %s", doc.metadata)
