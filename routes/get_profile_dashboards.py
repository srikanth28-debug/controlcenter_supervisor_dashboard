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
profiletable = dynamodb.Table("teco-user-permission-react-table")
dashboardtable = dynamodb.Table("teco-profile-permissions-react-table")

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

def handle_get_profile_dashboard(email):

    

    try:
        

        if not email:
            return respond(400, {"error": "Email not found in token"})

        # 2. Query DB1 for security profile
        res1 = profiletable.get_item(Key={"username": email})
        if "Item" not in res1:
            return respond(404, {"error": "User not found"})

        securityprofile = res1["Item"]["securityprofile"]
        team = res1["Item"]["team"]

        # Step 2: Query Table2 using (securityprofile, team)
        res2 = dashboardtable.get_item(
            Key={
                "securityprofile": securityprofile,
                "team": team
            }
        )

        if "Item" not in res2:
            return respond(404, {"error": "No tab config found"})

        tab_list = res2["Item"].get("tabnames", [])

        # 4. Return combined result
        return respond(200, {
            "email": email,
            "securityProfile": securityprofile,
            "tabs": tab_list
        })      

    except Exception as e:
        logger.exception("Unhandled error during get")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
