from utils.aws_clients import connect
from utils.logger import get_logger
from utils.http import respond
from botocore.exceptions import ClientError
import os
import json

# ---------------------------------------------------------------------------
# Logger and Connect client
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
CONNECT = connect

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
INSTANCE_ID = os.getenv("CONNECT_INSTANCE_ID")   # e.g., "33dd2811-cc53-...."
REGION = os.getenv("CONNECT_REGION", "us-west-2")

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_post_predefined_attributes(body: dict):

    name = (body or {}).get("name") or (body or {}).get("attributeName")
    raw_values = (body or {}).get("values") or (body or {}).get("StringList")

    # ---------------- Validation ----------------
    if not isinstance(name, str) or not name.strip():
        logger.warning("Missing or invalid 'name' in request body.")
        return respond(400, {
            "error": "BadRequest",
            "message": "Field 'name' is required."
        })

    if raw_values is None:
        logger.warning("Missing 'values' in request body.")
        return respond(400, {
            "error": "BadRequest",
            "message": "Field 'values' (array of strings) is required."
        })

    # Normalize values list
    if isinstance(raw_values, str):
        values = [raw_values.strip()]
    elif isinstance(raw_values, list):
        values = [str(v).strip() for v in raw_values if str(v).strip()]
    else:
        logger.warning(f"Invalid type for 'values': {type(raw_values)}")
        return respond(400, {
            "error": "BadRequest",
            "message": "Field 'values' must be a string or array of strings."
        })

    if not values:
        logger.warning("Empty values list after normalization.")
        return respond(400, {
            "error": "BadRequest",
            "message": "Field 'values' cannot be empty."
        })

    # ---------------- AWS Call ----------------
    try:
        logger.info(f"[CREATE] Creating predefined attribute '{name}' with {len(values)} value(s) in instance {INSTANCE_ID}")

        CONNECT.create_predefined_attribute(
            InstanceId=INSTANCE_ID,
            Name=name.strip(),
            Values={"StringList": values}
        )

        logger.info(f"[CREATE SUCCESS] Attribute '{name}' created successfully.")
        return respond(201, {
            "created": True,
            "name": name.strip(),
            "values": values,
            "message": f"Predefined attribute '{name.strip()}' was created."
        })

    # ---------------- AWS ClientError Handling ----------------
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

        logger.warning(f"[CREATE FAILED] [{code}] {msg} (RequestId={req_id})")
        return respond(status, {
            "error": code,
            "message": msg,
            "name": name,
            "values": values,
            "requestId": req_id
        })

    # ---------------- Generic Exception ----------------
    except Exception as e:
        logger.exception("[CREATE ERROR] Unhandled exception during attribute creation.")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
