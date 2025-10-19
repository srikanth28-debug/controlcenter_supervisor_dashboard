from utils.logger import get_logger
from utils.http import respond
import boto3
import base64
import json
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
POLLY = boto3.client("polly")

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_post_speech(body: dict):

    logger.info("[REQUEST] Handling post speech synthesis")

    # Extract and validate inputs
    text = body.get("text")
    voice_id = body.get("voice")
    output_format = body.get("output_format", "mp3")
    engine = body.get("engine", "neural")
    language_code = body.get("language_code", "en-US")
    text_type = body.get("text_type", "text")

    # -------------------- Validation --------------------
    if not text or not voice_id:
        logger.warning("[VALIDATION] Missing required fields: text or voice_id")
        return respond(400, {
            "error": "BadRequest",
            "message": "Fields 'text' and 'voice' are required."
        })

    try:
        # -------------------- Polly Synthesis --------------------
        logger.info(f"[POLLY] Synthesizing with Voice={voice_id}, Engine={engine}, Lang={language_code}")
        response = POLLY.synthesize_speech(
            Engine=engine,
            LanguageCode=language_code,
            TextType=text_type,
            Text=text,
            OutputFormat=output_format,
            VoiceId=voice_id
        )

        audio_stream = response.get("AudioStream")
        if not audio_stream:
            logger.error("[ERROR] Polly returned no AudioStream")
            return respond(502, {
                "error": "AudioStreamMissing",
                "message": "No audio data returned by Polly."
            })

        # Convert audio to base64 for client use
        audio_bytes = audio_stream.read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        logger.info(f"[SUCCESS] Synthesized {len(audio_bytes)} bytes of audio")

        return respond(200, {
            "audio": audio_base64,
            "voice": voice_id,
            "format": output_format,
            "engine": engine,
            "language_code": language_code
        })

    # -------------------- AWS Error Handling --------------------
    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        logger.warning(f"[AWS ERROR] {code}: {msg}")
        return respond(502, {
            "error": code,
            "message": msg
        })

    # -------------------- General Error Handling --------------------
    except Exception as e:
        logger.exception("[UNHANDLED ERROR] Polly speech synthesis failed")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
