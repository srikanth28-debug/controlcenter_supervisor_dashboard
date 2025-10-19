from utils.logger import get_logger
from utils.http import respond
import boto3
import os
import json
import base64

# ---------------------------------------------------------------------------
# Logger and AWS setup
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
S3 = boto3.client("s3")

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
AGENT_GREETING_BUCKET = os.getenv("AGENT_GREETING_BUCKET")
PRESIGNED_URL_EXPIRY_TIME = int(os.getenv("PRESIGNED_URL_EXPIRY_TIME", "3600"))  # default 1 hour

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_post_greetings(body: dict):
    """
    Handles uploading an agent greeting (Base64-encoded WAV) to S3 and returns
    a presigned URL for playback.

    Expected JSON body:
    {
        "username": "john.doe",
        "language": "en",
        "greeting": "<base64 encoded audio>"
    }
    """

    username = body.get("username")
    language = body.get("language")
    greeting_base64 = body.get("greeting")

    # ---------------- Validation ----------------
    if not username or not language or not greeting_base64:
        logger.warning("Missing username, language, or greeting in request body.")
        return respond(400, {
            "error": "BadRequest",
            "message": "Missing 'username', 'language', or 'greeting' in request body."
        })

    key = f"agent-greetings/{username}/{language}/agent_greeting.wav"
    logger.info(f"[UPLOAD] User={username}, Lang={language}, Key={key}")

    try:
        # Decode Base64 audio data
        audio_bytes = base64.b64decode(greeting_base64)
        logger.info(f"[UPLOAD] Decoded Base64 audio ({len(audio_bytes)} bytes)")

        # Upload file to S3
        S3.put_object(
            Bucket=AGENT_GREETING_BUCKET,
            Key=key,
            Body=audio_bytes,
            ContentType="audio/wav"
        )
        logger.info(f"[UPLOAD SUCCESS] Greeting stored in S3: s3://{AGENT_GREETING_BUCKET}/{key}")

        # Generate presigned URL for immediate playback
        presigned_url = S3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AGENT_GREETING_BUCKET, "Key": key},
            ExpiresIn=PRESIGNED_URL_EXPIRY_TIME
        )

        logger.info(f"[SIGNED URL] {presigned_url}")

        return respond(200, {"presignedUrl": presigned_url})

    except Exception as e:
        logger.exception("[ERROR] Failed to upload greeting")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
