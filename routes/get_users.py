from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import os
import json
import boto3
from botocore.exceptions import ClientError

# Env vars in Lambda config
INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]
REGION      = os.environ.get("CONNECT_REGION", "us-west-2")

connect = CONNECT

def _paginate_users(instance_id):
    paginator = connect.get_paginator("list_users")
    for page in paginator.paginate(InstanceId=instance_id):
        for u in page.get("UserSummaryList", []):
            yield u

def _format_name(identity_info):
    first = (identity_info or {}).get("FirstName") or ""
    last  = (identity_info or {}).get("LastName") or ""
    if first or last:
        return f"{last}, {first}".strip(", ").strip()
    return "-"

def _shape_proficiency(p):
    # Example item: {"AttributeName":"skill_name","AttributeValue":"outage","Level":1.0}
    attr = p.get("AttributeName")
    val  = p.get("AttributeValue")
    level = p.get("Level")
    if attr and val:
        label = f"{attr}={val}"
    else:
        # fallback if future variants appear
        label = p.get("Name") or attr or "Unknown"
    # Normalize 1.0 -> 1
    try:
        if isinstance(level, float) and level.is_integer():
            level = int(level)
    except Exception:
        pass
    return {"label": str(label), "level": level}

def handle_get_users():

    try:
        items = []

        for summary in _paginate_users(INSTANCE_ID):
            user_id = summary["Id"]

            # Get username + first/last
            try:
                user = connect.describe_user(InstanceId=INSTANCE_ID, UserId=user_id)["User"]
            except ClientError as e:
                print(f"DescribeUser failed for {user_id}: {e}")
                continue

            login = user.get("Username", "-")
            name  = _format_name(user.get("IdentityInfo"))

            # Get proficiencies for this user
            try:
                resp = connect.list_user_proficiencies(InstanceId=INSTANCE_ID, UserId=user_id)
                # Your payload uses 'UserProficiencyList'
                prof_list = resp.get("UserProficiencyList", [])
                # Fallback for other SDKs/shapes if ever needed
                if not prof_list and "Proficiencies" in resp:
                    prof_list = resp.get("Proficiencies", [])
            except ClientError as e:
                print(f"ListUserProficiencies failed for {login} ({user_id}): {e}")
                prof_list = []

            items.append({
                "login": login,
                "name": name,
                "user_id": user_id,
                "proficiencies": [_shape_proficiency(p) for p in prof_list]
            })

        items.sort(key=lambda r: (r["login"] or "").lower())
        print(f"Returning {items}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization"
            },
            "body": json.dumps({"count": len(items), "items": items})
        }

    except Exception as e:
        print("Unhandled error:", e)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Internal Server Error"})
        }