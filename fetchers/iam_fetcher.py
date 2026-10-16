import logging
from langchain_core.documents import Document
from fetchers.common import (
    AWS_ERRORS, get_boto3_client, paginate, record_fetch_failure
)

logger = logging.getLogger(__name__)


def _lookup(client, operation, result_key, field, **kwargs):
    """Paginated sub-lookup returning `field` of each item, or [] on error."""
    try:
        return [item[field] for item in paginate(client, operation, result_key, **kwargs)]
    except AWS_ERRORS as e:
        logger.warning("IAM %s failed for %s: %s", operation, kwargs, e)
        return []


def fetch_iam_users():
    """Fetch all IAM users and their details."""
    docs = []
    try:
        client = get_boto3_client("iam")
        users = paginate(client, "list_users", "Users")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_iam", "users", e)
        return docs

    for user in users:
        # Get user groups
        groups = _lookup(client, "list_groups_for_user", "Groups",
                         "GroupName", UserName=user["UserName"])

        # Get attached policies
        policies = _lookup(client, "list_attached_user_policies",
                           "AttachedPolicies", "PolicyName",
                           UserName=user["UserName"])

        # Check MFA
        try:
            mfa_devices = paginate(client, "list_mfa_devices", "MFADevices",
                                   UserName=user["UserName"])
            mfa_enabled = len(mfa_devices) > 0
        except AWS_ERRORS as e:
            logger.warning("IAM MFA lookup failed for %s: %s", user["UserName"], e)
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
    docs = []
    try:
        client = get_boto3_client("iam")
        roles = paginate(client, "list_roles", "Roles")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_iam", "roles", e)
        return docs

    for role in roles:
        # Skip AWS service roles
        if "aws-service-role" in role["RoleName"]:
            continue

        # Get attached policies
        policies = _lookup(client, "list_attached_role_policies",
                           "AttachedPolicies", "PolicyName",
                           RoleName=role["RoleName"])

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
    docs = []
    try:
        client = get_boto3_client("iam")
        groups = paginate(client, "list_groups", "Groups")
    except AWS_ERRORS as e:
        record_fetch_failure("aws_iam", "groups", e)
        return docs

    for group in groups:
        # Get group policies
        policies = _lookup(client, "list_attached_group_policies",
                           "AttachedPolicies", "PolicyName",
                           GroupName=group["GroupName"])

        # Get group members
        members = _lookup(client, "get_group", "Users", "UserName",
                          GroupName=group["GroupName"])

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
    try:
        client = get_boto3_client("iam")
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
    except AWS_ERRORS as e:
        record_fetch_failure("aws_iam", "account summary", e)
        return []


def fetch_all_iam_data():
    """Fetch all IAM related data."""
    docs = []
    logger.info("Fetching IAM summary...")
    docs.extend(fetch_iam_summary())
    logger.info("Fetching IAM users...")
    docs.extend(fetch_iam_users())
    logger.info("Fetching IAM roles...")
    docs.extend(fetch_iam_roles())
    logger.info("Fetching IAM groups...")
    docs.extend(fetch_iam_groups())
    logger.info("IAM fetcher done — %d documents", len(docs))
    return docs


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    docs = fetch_all_iam_data()
    logger.info("\nTotal docs: %d", len(docs))
    logger.info("\nSample:")
    for doc in docs[:3]:
        logger.info("\n%s", doc.page_content)
        logger.info("Metadata: %s", doc.metadata)
