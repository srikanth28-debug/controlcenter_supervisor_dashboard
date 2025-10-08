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
table = dynamodb.Table("teco-user-permission-react-table")

def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    }

def _deprecated_local_response(status_code: int, payload: dict):
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(payload),
    }

def handle_user_configs(body):
    username = body.get("username")

    try:
        logger.info(f"Get email templates for routingProfile={username}")

        # body = json.loads(event.get("body", "{}"))
        action = body.get("action")

        if action == "create":
            table.put_item(
                Item={
                    "username": body["username"],
                    "team": body["team"],
                    "securityprofile": body["securityprofile"]
                }
            )

            return _response(200, {
            "message": "User created"
            })

        elif action == "update":
            table.update_item(
                Key={"username": body["username"]},
                UpdateExpression="SET team = :t, securityprofile = :a",
                ExpressionAttributeValues={
                    ":t": body["team"],
                    ":a": body["securityprofile"]
                }
            )

            return _response(200, {
            "message": "User updated"
            })

        elif action == "delete":
            table.delete_item(Key={"username": body["username"]})
            return _response(200, {
            "message": "User deleted"
            })

        elif action == "list":
            res = table.scan()
            return _response(200, {"users": res["Items"]})

        elif action == "listTeamsProfiles":
            # Scan the table to discover all unique teams and security profiles
            res = table.scan()
            items = res.get("Items", [])

            teams = sorted({item.get("team", "") for item in items if "team" in item})
            profiles = sorted({item.get("securityprofile", "") for item in items if "securityprofile" in item})

            return _response(200, {
                "teams": list(teams),
                "securityprofiles": list(profiles)
            })    

        else:
            return _response(200, {"error": "Invalid action"})      

    except Exception as e:
        logger.exception("Unhandled error during get")
        return _response(500, {
            "error": "InternalServerError",
            "message": str(e)
        })

from utils.http import respond as __respond, cors_headers as __cors_headers
from utils.logger import get_logger as __get_logger
from utils.aws_clients import ddb as __DDB, connect as __CONNECT, table as __table

# Standardize helpers across routes (backwards-compatible)
try:
    _response
except NameError:
    _response = __respond
try:
    _cors_headers
except NameError:
    _cors_headers = __cors_headers
try:
    DDB
except NameError:
    DDB = __DDB
try:
    CONNECT
except NameError:
    CONNECT = __CONNECT

