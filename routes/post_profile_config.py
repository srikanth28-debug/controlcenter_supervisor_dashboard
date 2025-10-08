from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import os
import urllib.parse
import logging
import json
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = DDB
table = dynamodb.Table("teco-profile-permissions-react-table")

def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    }

def respond(status_code: int, payload: dict):
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(payload),
    }

def handle_profile_configs(body):
    securityprofile = body.get("securityprofile")

    try:
        logger.info(f"Get email templates for routingProfile={securityprofile}")

        # body = json.loads(event.get("body", "{}"))
        action = body.get("action")

        if action == "create":
            table.put_item(
                Item={
                    "securityprofile": body["securityprofile"],
                    "team": body["team"],
                    "tabnames": body["tabnames"]                   
                }
            )

            return respond(200, {
            "message": "User created"
            })

        elif action == "update":
            table.update_item(
                Key={"securityprofile": body["securityprofile"], "team": body["team"]},
                UpdateExpression="SET tabnames = :t",
                ExpressionAttributeValues={
                    ":t": body["tabnames"]
                }
            )

            return respond(200, {
            "message": "User updated"
            })

        elif action == "delete":
            table.delete_item(Key={"securityprofile": body["securityprofile"], "team": body["team"]})
            return respond(200, {
            "message": "User deleted"
            })

        elif action == "list":
            res = table.scan()
            return respond(200, {"users": res["Items"]})

        elif action == "listTeamsTabs":
            res = table.scan()
            items = res.get("Items", [])

            # collect unique team names
            teams = sorted({item["team"] for item in items})

            # flatten all tabnames and unique them
            tabs = set()
            for item in items:
                if "tabnames" in item:
                    # each tabnames element is either string or dict {"S": "Name"}
                    for t in item["tabnames"]:
                        if isinstance(t, dict) and "S" in t:
                            tabs.add(t["S"])
                        else:
                            tabs.add(t)
            return respond(200, {"teams": list(teams), "tabs": list(tabs)})    

        else:
            return respond(200, {"error": "Invalid action"})      

    except Exception as e:
        logger.exception("Unhandled error during get")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
