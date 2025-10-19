from utils.aws_clients import connect
from utils.logger import get_logger
from utils.http import respond
from botocore.exceptions import ClientError
import os
import json

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
INSTANCE_ID = os.getenv("CONNECT_INSTANCE_ID")
REGION = os.getenv("CONNECT_REGION", "us-west-2")

CONNECT = connect

# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------
def handle_delete_predefined_attributes(path_params):
    """
    Deletes a predefined attribute from an Amazon Connect instance.
    Route: /business-configuration/predefined-attributes/{attributeName+}
    """

    attribute_name = path_params.get("attributeName")
    if not attribute_name:
        return respond(400, {
            "error": "BadRequest",
            "message": "Path parameter 'attributeName' is required."
        })

    try:
        logger.info(f"[DELETE] Predefined attribute '{attribute_name}' in instance {INSTANCE_ID}")

        CONNECT.delete_predefined_attribute(
            InstanceId=INSTANCE_ID,
            Name=attribute_name
        )

        logger.info(f"[DELETE SUCCESS] Attribute '{attribute_name}' deleted successfully.")
        return respond(200, {
            "deleted": True,
            "name": attribute_name,
            "message": f"Predefined attribute '{attribute_name}' was deleted."
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

        logger.warning(f"[DELETE FAILED] [{code}] {msg} (RequestId={req_id})")
        return respond(status, {
            "error": code,
            "message": msg,
            "name": attribute_name,
            "requestId": req_id
        })

    except Exception as e:
        logger.exception("[DELETE EXCEPTION] Unhandled error during attribute delete")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
