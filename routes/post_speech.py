import boto3
import base64
import logging
import json
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLLY = boto3.client("polly")

def handle_post_speech(body):

    logger.info("Handling post speech request")
        
    text = body.get("text", None)
    voice_id = body.get("voice", None)
    output_format = body.get("output_format", "mp3")
    engine = body.get("engine", None)
    language_code = body.get("language_code", None)
    text_type = body.get("text_type", None)

    '''
    if not text or not voice_id or not output_format:
        return {
            'statusCode': 400,
            'body': json.dumps({"error": "Missing neccessary data."}),
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        }
    '''

    response = POLLY.synthesize_speech(
        Engine=engine,
        LanguageCode=language_code,
        TextType=text_type,
        Text=text,
        OutputFormat=output_format,
        VoiceId=voice_id
    )

    audio_stream = response['AudioStream'].read()
    audio_base64 = base64.b64encode(audio_stream).decode('utf-8')

    return {
            'statusCode': 200,
            'body': json.dumps({
                "audio": audio_base64
            }),
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

