from utils.logger import get_logger
from utils.http import respond
import boto3
import os
import json

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# AWS S3 Client
# ---------------------------------------------------------------------------
S3 = boto3.client("s3")

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
AGENT_GREETING_BUCKET = os.getenv("AGENT_GREETING_BUCKET")
PRESIGNED_URL_EXPIRY_TIME = int(os.getenv("PRESIGNED_URL_EXPIRY_TIME", "3600"))  # Default: 1 hour

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_get_greetings(username: str, language: str):
    """
    Generates a presigned URL for retrieving an agent greeting audio file from S3.
    
    S3 Key structure:
        agent-greetings/{username}/{language}/agent_greeting.wav

    Environment Variables:
        AGENT_GREETING_BUCKET          -> Target S3 bucket
        PRESIGNED_URL_EXPIRY_TIME      -> Expiration (seconds)
    """

    if not username or not language:
        logger.warning("Missing 'username' or 'language' parameter")
        return respond(400, {
            "error": "BadRequest",
            "message": "Both 'username' and 'language' query parameters are required."
        })

    try:
        key = f"agent-greetings/{username}/{language}/agent_greeting.wav"
        logger.info(f"[GET GREETING] Generating presigned URL for key: {key}")

        presigned_url = S3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AGENT_GREETING_BUCKET, "Key": key},
            ExpiresIn=PRESIGNED_URL_EXPIRY_TIME
        )

        logger.info(f"[SUCCESS] Presigned URL generated for user={username}, language={language}")

        return respond(200, {"presignedUrl": presigned_url})

    except Exception as e:
        logger.exception("[ERROR] Failed to generate presigned URL")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
