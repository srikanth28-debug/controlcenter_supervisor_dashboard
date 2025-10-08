from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import os
import urllib.parse
import logging
import json
import base64

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3 = boto3.client('s3')
AGENT_GREETING_BUCKET = os.environ['AGENT_GREETING_BUCKET']

def handle_post_greetings(body):
    username = body.get("username", None)
    language = body.get("language", None)
    greeting_base64 = body.get("greeting", None)

    if not username or not language or not greeting_base64:
        return {
            'statusCode': 400,
            'body': json.dumps({"error": "Missing username, language, or greeting"}),
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        }

    logger.info(f"Username: {username}")
    logger.info(f"Language: {language}")

    key = f"agent-greetings/{username}/{language}/agent_greeting.wav"
    logger.info(f"Key: {key}")

    try:
        # Decode the base64 string to binary WAV data
        audio_bytes = base64.b64decode(greeting_base64)

        # Upload to S3
        S3.put_object(
            Bucket=AGENT_GREETING_BUCKET,
            Key=key,
            Body=audio_bytes,
            ContentType='audio/wav'
        )

        # Generate a pre-signed URL (optional)
        presigned_url = S3.generate_presigned_url(
            'get_object',
            Params={'Bucket': AGENT_GREETING_BUCKET, 'Key': key},
            ExpiresIn=3600  # 1 hour
        )

        return {
            'statusCode': 200,
            'body': json.dumps({"presignedUrl": presigned_url}),
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        }

    except Exception as e:
        logger.error(f"Error uploading greeting: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({"error": "Failed to store greeting"}),
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        }
