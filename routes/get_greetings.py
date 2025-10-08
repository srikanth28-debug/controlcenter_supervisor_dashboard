import boto3
import os
import urllib.parse
import logging
import json

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3 = boto3.client('s3')

AGENT_GREETING_BUCKET = os.environ['AGENT_GREETING_BUCKET']
PRESIGNED_URL_EXPIRY_TIME = os.environ['PRESIGNED_URL_EXPIRY_TIME']

def handle_get_greetings(username, language):

    key = f"agent-greetings/{username}/{language}/agent_greeting.wav"
    logger.info(f"Key: {key}")

    presigned_url = S3.generate_presigned_url(
        'get_object',
        Params={'Bucket': AGENT_GREETING_BUCKET, 'Key': key},
        ExpiresIn=PRESIGNED_URL_EXPIRY_TIME
    )
    logger.info(f"Presigned URL: {presigned_url}")

    return {
        'statusCode': 200,
        'body': json.dumps({"presignedUrl": presigned_url}),
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    }

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

