from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import os
import urllib.parse
import logging
import json
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Env vars in Lambda config
INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]
REGION      = os.environ.get("CONNECT_REGION", "us-west-2")

connect = CONNECT
dynamodb = DDB
table = dynamodb.Table("teco_email_templates")

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

def _json_safe(obj):
    """Recursively convert DynamoDB types (set, Decimal) to JSON-serializable ones."""
    if isinstance(obj, set):
        return sorted(list(obj))
    if isinstance(obj, Decimal):
        # Convert integral Decimals to int, others to float
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj

def handle_get_email_template_app(path_params):
    routing_profile_name = path_params.get("routingProfile")

    try:
        logger.info(f"Get email templates for routingProfile={routing_profile_name}")

        response = table.scan(
            FilterExpression=Attr("routing_profile").contains(routing_profile_name)
        )

        items = response.get("Items", [])
        items.sort(key=lambda x: (x.get("template_name") or "").lower())
        items = _json_safe(items)  # <-- make JSON-safe

        logger.info(f"Found {len(items)} items")

        return respond(200, {
            "name": routing_profile_name,
            "templates": items
        })

    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        req_id = e.response.get("ResponseMetadata", {}).get("RequestId")

        status_map = {
            "AccessDeniedException": 403,
            "ResourceInUseException": 409,
            "ResourceNotFoundException": 404,
            "InvalidRequestException": 400,
            "InvalidParameterException": 400,
            "ThrottlingException": 429,
            "InternalServiceException": 502,
        }
        status = status_map.get(code, 502)

        logger.warning(f"Get templates failed [{code}] {msg} (requestId={req_id})")
        return respond(status, {
            "error": code,
            "message": msg,
            "name": routing_profile_name,
            "requestId": req_id
        })

    except Exception as e:
        logger.exception("Unhandled error during get")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
