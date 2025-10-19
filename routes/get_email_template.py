from utils.aws_clients import table
from utils.logger import get_logger
from utils.http import respond
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr
from decimal import Decimal
import os
import json

# ---------------------------------------------------------------------------
# Logger and environment setup
# ---------------------------------------------------------------------------
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# DynamoDB table (from env)
# ---------------------------------------------------------------------------
EMAIL_TEMPLATES_TABLE = table("DDB_TABLE_TECO_EMAIL_TEMPLATES", "teco_email_templates")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _json_safe(obj):
    """Recursively convert DynamoDB types (set, Decimal) to JSON-safe primitives."""
    if isinstance(obj, set):
        return sorted(list(obj))
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_get_email_template_app(path_params: dict):
    """
    Fetches all email templates from DynamoDB filtered by routing profile.
    API route example: GET /email-templates/{routingProfile}
    """

    routing_profile_name = path_params.get("routingProfile")

    if not routing_profile_name:
        logger.warning("Missing 'routingProfile' path parameter")
        return respond(400, {"error": "BadRequest", "message": "'routingProfile' is required"})

    try:
        logger.info(f"[GET] Fetching email templates for routingProfile={routing_profile_name}")

        response = EMAIL_TEMPLATES_TABLE.scan(
            FilterExpression=Attr("routing_profile").contains(routing_profile_name)
        )

        items = response.get("Items", [])
        items.sort(key=lambda x: (x.get("template_name") or "").lower())
        safe_items = _json_safe(items)

        logger.info(f"[GET SUCCESS] Found {len(safe_items)} templates for routingProfile={routing_profile_name}")

        return respond(200, {
            "name": routing_profile_name,
            "templates": safe_items
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

        logger.warning(f"[GET FAILED] [{code}] {msg} (requestId={req_id})")
        return respond(status, {
            "error": code,
            "message": msg,
            "name": routing_profile_name,
            "requestId": req_id
        })

    except Exception as e:
        logger.exception("[UNHANDLED ERROR] During email template retrieval")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
