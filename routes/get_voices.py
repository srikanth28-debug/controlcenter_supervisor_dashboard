from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
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

    

