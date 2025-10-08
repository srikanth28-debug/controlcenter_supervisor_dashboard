from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import os
import urllib.parse
import logging
import json
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Env vars in Lambda config
INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]   # e.g. "33dd2811-cc53-...."
REGION      = os.environ.get("CONNECT_REGION", "us-west-2")

connect = CONNECT

def _iso(dt):
    if not dt:
        return None
    try:
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return str(dt)

def _paginate_list_predefined_attributes(instance_id):
    paginator = connect.get_paginator("list_predefined_attributes")
    for page in paginator.paginate(InstanceId=instance_id):
        for s in page.get("PredefinedAttributeSummaryList", []):
            yield s

def _describe_attribute(instance_id, name):
    resp = connect.describe_predefined_attribute(InstanceId=instance_id, Name=name)
    pa = resp.get("PredefinedAttribute", {}) or {}
    values_obj = pa.get("Values") or {}
    values = values_obj.get("StringList", [])  # union — API returns this array
    return {
        "name": pa.get("Name") or name,
        "values": values,
        "lastModifiedTime": _iso(pa.get("LastModifiedTime")),
        "lastModifiedRegion": pa.get("LastModifiedRegion"),
    }

def handle_get_predefined_attributes():

    try:
        # Build both a list and a map, so the UI can bind easily
        attributes = []
        value_options_by_attribute = {}

        for summary in _paginate_list_predefined_attributes(INSTANCE_ID):
            name = summary.get("Name")
            if not name:
                continue
            detail = _describe_attribute(INSTANCE_ID, name)
            attributes.append({"name": detail["name"], "values": detail["values"]})
            value_options_by_attribute[detail["name"]] = detail["values"]

        # Sort for stable dropdown order
        attributes.sort(key=lambda a: a["name"].lower())
        attribute_options = [a["name"] for a in attributes]

        body = {
            "attributeOptions": attribute_options,                 # ["connect:Subtype", "skill_name", ...]
            "valueOptionsByAttribute": value_options_by_attribute, # { "connect:Subtype": ["connect:Chat", ...], ... }
        }
        print(f"Returning {body}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
            },
            "body": json.dumps(body),
        }

    except ClientError as e:
        print("AWS error:", e)
        return {
            "statusCode": 502,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "Upstream AWS error", "detail": str(e)}),
        }
    except Exception as e:
        print("Unhandled error:", e)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "Internal Server Error"}),
        }