from utils.logger import get_logger
from utils.http import respond
import boto3
import json
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Logger & Polly client
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
POLLY = boto3.client("polly")

# ---------------------------------------------------------------------------
# Helper: List supported voices
# ---------------------------------------------------------------------------
def get_supported_voices():

    voices = []
    try:
        paginator = POLLY.get_paginator("describe_voices")
        for page in paginator.paginate():
            voices.extend(page.get("Voices", []))
    except Exception as e:
        logger.exception("[ERROR] Failed to retrieve Polly voices")
        raise
    return voices

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_get_voices():
    
    logger.info("[REQUEST] Handling get voices request")

    try:
        voices = get_supported_voices()
        logger.info(f"[SUCCESS] Retrieved {len(voices)} voices from Polly")

        return respond(200, {"voices": voices})

    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        logger.warning(f"[AWS ERROR] {code}: {msg}")
        return respond(502, {"error": code, "message": msg})

    except Exception as e:
        logger.exception("[UNHANDLED ERROR] Fetching voices from Polly")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
