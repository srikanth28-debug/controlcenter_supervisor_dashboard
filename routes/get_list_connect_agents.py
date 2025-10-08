from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Connect client
connect_client = CONNECT
INSTANCE_ID = "5ad694d7-d5f2-434d-9c35-e6369cbd77e7"

def handle_get_list_connect_agents():
    """
    Fetch all Amazon Connect agents and return simplified list
    """
    try:
        logger.info("Fetching agent list from Connect")

        response = connect_client.list_users(
            InstanceId=INSTANCE_ID,
            MaxResults=100  # Adjust if needed
        )

        # Extract agent login & names
        agents = []
        for user in response.get("UserSummaryList", []):
            agents.append({
                "agent_login": user.get("Username"),
                "agent_name": (
                    (user.get("IdentityInfo", {}).get("FirstName", "") + " " +
                     user.get("IdentityInfo", {}).get("LastName", "")).strip()
                ),
                "agent_id": user.get("Id")
            })

        logger.info(f"Fetched {len(agents)} agents")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"agents": agents})
        }

    except Exception as e:
        logger.error(f"Error fetching agents: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }
