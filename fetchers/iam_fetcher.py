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

def fetch_iam_users():
    """Fetch all IAM users and their details."""
    client = get_boto3_client("iam")
    paginator = client.get_paginator("list_users")

    docs = []
    for page in paginator.paginate():
        for user in page["Users"]:
            # Get user groups
            try:
                groups_response = client.list_groups_for_user(
                    UserName=user["UserName"]
                )
                groups = [g["GroupName"] for g in groups_response["Groups"]]
            except:
                groups = []

            # Get attached policies
            try:
                policies_response = client.list_attached_user_policies(
                    UserName=user["UserName"]
                )
                policies = [p["PolicyName"] for p in policies_response["AttachedPolicies"]]
            except:
                policies = []

            # Check MFA
            try:
                mfa_response = client.list_mfa_devices(
                    UserName=user["UserName"]
                )
                mfa_enabled = len(mfa_response["MFADevices"]) > 0
            except:
                mfa_enabled = False

            text = f"""IAM User:
Username: {user['UserName']}
User ID: {user['UserId']}
Created: {user['CreateDate'].strftime('%Y-%m-%d')}
Last Login: {user.get('PasswordLastUsed', 'Never').strftime('%Y-%m-%d') if hasattr(user.get('PasswordLastUsed', 'Never'), 'strftime') else 'Never'}
MFA Enabled: {mfa_enabled}
Groups: {', '.join(groups) if groups else 'None'}
Attached Policies: {', '.join(policies) if policies else 'None'}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_iam",
                    "username": user["UserName"],
                    "mfa_enabled": mfa_enabled,
                    "type": "iam_user"
                }
            ))
    return docs


def fetch_iam_roles():
    """Fetch all IAM roles."""
    client = get_boto3_client("iam")
    paginator = client.get_paginator("list_roles")

    docs = []
    for page in paginator.paginate():
        for role in page["Roles"]:
            # Skip AWS service roles
            if "aws-service-role" in role["RoleName"]:
                continue

            # Get attached policies
            try:
                policies_response = client.list_attached_role_policies(
                    RoleName=role["RoleName"]
                )
                policies = [p["PolicyName"] for p in policies_response["AttachedPolicies"]]
            except:
                policies = []

            text = f"""IAM Role:
Name: {role['RoleName']}
Role ID: {role['RoleId']}
Created: {role['CreateDate'].strftime('%Y-%m-%d')}
Description: {role.get('Description', 'No description')}
Attached Policies: {', '.join(policies) if policies else 'None'}
ARN: {role['Arn']}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_iam",
                    "role_name": role["RoleName"],
                    "type": "iam_role"
                }
            ))
    return docs


def fetch_iam_groups():
    """Fetch all IAM groups."""
    client = get_boto3_client("iam")
    paginator = client.get_paginator("list_groups")

    docs = []
    for page in paginator.paginate():
        for group in page["Groups"]:
            # Get group policies
            try:
                policies_response = client.list_attached_group_policies(
                    GroupName=group["GroupName"]
                )
                policies = [p["PolicyName"] for p in policies_response["AttachedPolicies"]]
            except:
                policies = []

            # Get group members
            try:
                members_response = client.get_group(
                    GroupName=group["GroupName"]
                )
                members = [u["UserName"] for u in members_response["Users"]]
            except:
                members = []

            text = f"""IAM Group:
Name: {group['GroupName']}
Group ID: {group['GroupId']}
Created: {group['CreateDate'].strftime('%Y-%m-%d')}
Members: {', '.join(members) if members else 'None'}
Attached Policies: {', '.join(policies) if policies else 'None'}"""

            docs.append(Document(
                page_content=text,
                metadata={
                    "source": "aws_iam",
                    "group_name": group["GroupName"],
                    "type": "iam_group"
                }
            ))
    return docs


def fetch_iam_summary():
    """Fetch overall IAM account summary."""
    client = get_boto3_client("iam")

    try:
        summary = client.get_account_summary()
        data = summary["SummaryMap"]

        text = f"""IAM Account Summary:
Total Users: {data.get('Users', 0)}
Total Groups: {data.get('Groups', 0)}
Total Roles: {data.get('Roles', 0)}
Total Policies: {data.get('Policies', 0)}
MFA Devices: {data.get('MFADevices', 0)}
MFA Devices In Use: {data.get('MFADevicesInUse', 0)}
Access Keys: {data.get('AccessKeys', 0)}"""

        return [Document(
            page_content=text,
            metadata={"source": "aws_iam", "type": "iam_summary"}
        )]
    except Exception as e:
        print(f"IAM summary error: {e}")
        return []


def fetch_all_iam_data():
    """Fetch all IAM related data."""
    docs = []
    print("Fetching IAM summary...")
    docs.extend(fetch_iam_summary())
    print("Fetching IAM users...")
    docs.extend(fetch_iam_users())
    print("Fetching IAM roles...")
    docs.extend(fetch_iam_roles())
    print("Fetching IAM groups...")
    docs.extend(fetch_iam_groups())
    print(f"IAM fetcher done — {len(docs)} documents")
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = fetch_all_iam_data()
    print(f"\nTotal docs: {len(docs)}")
    print("\nSample:")
    for doc in docs[:3]:
        print(f"\n{doc.page_content}")
        print(f"Metadata: {doc.metadata}")