import boto3
import os
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

def fetch_ec2_instances():
    """Fetch all EC2 instances and their details."""
    client = get_boto3_client("ec2")
    response = client.describe_instances()

    docs = []
    for reservation in response["Reservations"]:
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
    client = get_boto3_client("ec2")
    response = client.describe_security_groups()

    docs = []
    for sg in response["SecurityGroups"]:
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
    client = get_boto3_client("ec2")
    response = client.describe_vpcs()

    docs = []
    for vpc in response["Vpcs"]:
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
    print("Fetching EC2 instances...")
    docs.extend(fetch_ec2_instances())
    print("Fetching security groups...")
    docs.extend(fetch_ec2_security_groups())
    print("Fetching VPCs...")
    docs.extend(fetch_ec2_vpcs())
    print(f"EC2 fetcher done — {len(docs)} documents")
    return docs


def load_uploaded_files(upload_path="./uploads"):
    docs = []
    if not os.path.exists(upload_path):
        return docs
    for filename in os.listdir(upload_path):
        if filename.startswith("."):  # skip hidden files
            continue
        file_path = os.path.join(upload_path, filename)

# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = fetch_all_ec2_data()
    print(f"\nTotal docs: {len(docs)}")
    print("\nSample:")
    for doc in docs[:3]:
        print(f"\n{doc.page_content}")
        print(f"Metadata: {doc.metadata}")