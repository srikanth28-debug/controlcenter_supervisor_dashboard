import os
import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CONNECT_INSTANCE_ID = os.getenv("CONNECT_INSTANCE_ID", "")

# Reusable Boto3 clients/resources
ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
connect = boto3.client("connect", region_name=AWS_REGION)

def table(name_env_key, default_name=None):
    """
    Returns a DynamoDB Table resource using an environment variable key.

    Example:
        users_table = table("USERS_TABLE_NAME", "teco-dynamodb-users-dev")
    """
    name = os.getenv(name_env_key, default_name)
    if not name:
        raise RuntimeError(f"Missing env var: {name_env_key}")
    return ddb.Table(name)
