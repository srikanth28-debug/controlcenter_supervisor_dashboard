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
INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]
REGION      = os.environ.get("CONNECT_REGION", "us-west-2")

connect = CONNECT

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

def handle_delete_predefined_attributes(path_params):
    """
    Expected route: /business-configuration/predefined-attributes/{attributeName+}
    In API Gateway, the key in pathParameters will be 'attributeName' (greedy '+'
    is not part of the key name). We still defensively check for both.
    """

    attribute_name = path_params.get("attributeName", None)

    if attribute_name is None:
        return _response(400, {
            "error": "BadRequest",
            "message": "Path parameter 'attributeName' is required."
        })

    try:
        logger.info(f"Deleting predefined attribute: '{attribute_name}' in instance {INSTANCE_ID}")

        connect.delete_predefined_attribute(
            InstanceId = INSTANCE_ID,
            Name = attribute_name
        )

        return _response(200, {
            "deleted": True,
            "name": attribute_name,
            "message": f"Predefined attribute '{attribute_name}' was deleted."
        })

    except ClientError as e:
        # Surface AWS error details to the frontend
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        req_id = e.response.get("ResponseMetadata", {}).get("RequestId")

        # Map common Connect errors to sensible HTTP status
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

        logger.warning(f"Delete failed [{code}] {msg} (requestId={req_id})")
        return _response(status, {
            "error": code,
            "message": msg,
            "name": attribute_name,
            "requestId": req_id
        })

    except Exception as e:
        logger.exception("Unhandled error during delete")
        return _response(500, {
            "error": "InternalServerError",
            "message": str(e)  # you can omit this in prod if you prefer
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

