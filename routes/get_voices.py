import boto3
import json
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLLY = boto3.client('polly')

def get_supported_voices():
    
    response = POLLY.describe_voices()

    return response['Voices']

def handle_get_voices():

    logger.info("Handling get voices request")
    
    voices = get_supported_voices()

    return_object = {
        'statusCode': 200,
        'body': json.dumps({"voices": voices}),
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    }

    logger.info(f"Returning: {return_object}")

    return return_object

    


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

