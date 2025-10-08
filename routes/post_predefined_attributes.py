from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import os
import json
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Env vars in Lambda config
INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]   # e.g. "33dd2811-cc53-...."
REGION      = os.environ.get("CONNECT_REGION", "us-west-2")

connect = CONNECT

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

def handle_post_predefined_attributes(body: dict):
    """
    Expected JSON body:
      {
        "name": "Skill",
        "values": ["Gold", "Silver", "Bronze"]   # or "StringList": [...]
      }
    No de-duplication is performed here.
    """
    name = (body or {}).get("name") or (body or {}).get("attributeName")
    raw_values = (body or {}).get("values") or (body or {}).get("StringList")

    # Basic validation
    if not isinstance(name, str) or not name.strip():
        return respond(400, {"error": "BadRequest", "message": "Field 'name' is required."})

    if raw_values is None:
        return respond(400, {"error": "BadRequest", "message": "Field 'values' (array of strings) is required."})

    # Normalize to a list of strings (preserve order, preserve duplicates)
    if isinstance(raw_values, str):
        values = [raw_values.strip()]
    elif isinstance(raw_values, list):
        # keep duplicates; only trim whitespace and drop empties
        values = [str(v).strip() for v in raw_values if str(v).strip() != ""]
    else:
        return respond(400, {"error": "BadRequest", "message": "Field 'values' must be a string or array of strings."})

    if not values:
        return respond(400, {"error": "BadRequest", "message": "Field 'values' cannot be empty."})

    try:
        logger.info(f"Creating predefined attribute '{name}' with {len(values)} value(s) in instance {INSTANCE_ID}")

        connect.create_predefined_attribute(
            InstanceId=INSTANCE_ID,
            Name=name.strip(),
            Values={"StringList": values}
        )

        return respond(201, {
            "created": True,
            "name": name.strip(),
            "values": values,
            "message": f"Predefined attribute '{name.strip()}' was created."
        })

    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        req_id = e.response.get("ResponseMetadata", {}).get("RequestId")

        status_map = {
            "AccessDeniedException": 403,
            "DuplicateResourceException": 409,
            "ResourceNotFoundException": 404,
            "InvalidRequestException": 400,
            "InvalidParameterException": 400,
            "LimitExceededException": 429,
            "ThrottlingException": 429,
            "InternalServiceException": 502,
        }
        status = status_map.get(code, 502)

        logger.warning(f"Create failed [{code}] {msg} (requestId={req_id})")
        return respond(status, {
            "error": code,
            "message": msg,
            "name": name,
            "values": values,
            "requestId": req_id
        })

    except Exception as e:
        logger.exception("Unhandled error during create")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
