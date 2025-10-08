import json
import logging
# from get_greetings import handle_get_greetings
# from post_greetings import handle_post_greetings
# from get_voices import handle_get_voices
# from post_speech import handle_post_speech
# from get_users import handle_get_users
# from get_predefined_attributes import handle_get_predefined_attributes
# from delete_predefined_attribute import handle_delete_predefined_attributes
# from post_predefined_attributes import handle_post_predefined_attributes
# from post_user_proficiencies import handle_post_user_proficiencies
# from post_user_proficiencies_bulk import handle_post_user_proficiencies_bulk
# from get_email_template import handle_get_email_template_app
# from post_task_template import handle_post_task_template_app
from post_chaneltype_configs import handle_chaneltype_configs
from post_chaneltype_prompts import handle_chaneltype_prompts
from post_user_config import handle_user_configs
from post_profile_config import handle_profile_configs
from get_profile_dashboards import handle_get_profile_dashboard
from get_list_connect_agents import handle_get_list_connect_agents
from post_agent_proficiency_profiles import handle_agent_proficiency_profiles
from post_agent_proficiency_assignment import handle_agent_proficiency_assignment
#from utils import create_response, create_error_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"Received event: {event}")

    resource = event.get('resource', '')
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')
    query_params = event.get('queryStringParameters', {})
    path_params = event.get('pathParameters', {})
    body = event.get('body', '{}')
    logger.info(f"Path: {path}, Resource: {resource}, Method: {http_method}")

    
    # --- CORS preflight for ALL routes ---
    if http_method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Max-Age": "600",
            },
            "body": json.dumps({"message": "ok"}),
        }
    
        

    if resource == '/agent-greeting' and http_method == 'GET':
        logger.info("Handling GET request for /agent-greeting")

        # Query String Parameters
        username = query_params.get('username', '')
        language = query_params.get('language', '')

        logger.info(f"Username: {username}")
        logger.info(f"Language: {language}")

        return handle_get_greetings(username, language)
    elif resource == '/agent-greeting' and http_method == 'POST':
        logger.info("Handling POST request for /agent-greeting")

        body = json.loads(event.get('body', '{}'))

        return handle_post_greetings(body)
    elif resource == '/polly/languages' and http_method == 'GET':
        logger.info("Handling GET request for /polly/languages")

        return handle_get_voices()
    elif resource == '/polly/speech' and http_method == 'POST':
        logger.info("Handling POST request for /polly/speech")

        body = json.loads(event.get('body', '{}'))

        return handle_post_speech(body)
    elif resource == '/business-configuration/users' and http_method == 'GET':
        logger.info("Handling GET request for /business-configuration/users")

        return handle_get_users()

    elif resource == '/business-configuration/predefined-attributes' and http_method == 'GET':
        logger.info("Handling GET request for /business-configuration/predefined-attributes")

        return handle_get_predefined_attributes()
    
    elif resource == '/business-configuration/predefined-attributes/{attributeName+}' and http_method == 'DELETE':
        logger.info("Handling DELETE request for /business-configuration/predefined-attributes")

        return handle_delete_predefined_attributes(path_params)

    elif resource == '/business-configuration/predefined-attributes' and http_method == 'POST':
        logger.info("Handling POST request for /business-configuration/predefined-attributes")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_post_predefined_attributes(body)

    elif resource == '/business-configuration/user-proficiencies' and http_method == 'POST':
        logger.info("Handling POST request for /business-configuration/user-proficiencies")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_post_user_proficiencies(body)
    elif resource == '/business-configuration/user-proficiencies-bulk' and http_method == 'POST':
        logger.info("Handling POST request for /business-configuration/user-proficiencies-bulk")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_post_user_proficiencies_bulk(body)
    elif resource == '/email-template-app/{routingProfile+}' and http_method == 'GET':
        logger.info("Handling GET request for /email-template-app/{routingProfile+}")

        return handle_get_email_template_app(path_params)
    elif resource == '/task-template-app' and http_method == 'POST':
        logger.info("Handling GET request for /teco-template-app")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_post_task_template_app(body)
    elif resource == '/chaneltypeconfigs' and http_method == 'POST':
        logger.info("Handling GET request for /teco-chaneltype-configs")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_chaneltype_configs(body) 
    elif resource == '/chaneltypeprompts' and http_method == 'POST':
        logger.info("Handling post request for /teco-chaneltype-prompts")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_chaneltype_prompts(body)      
    elif resource == '/userconfig' and http_method == 'POST':
        logger.info("Handling post request for /teco-user-config")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_user_configs(body)
    elif resource == '/profileconfig' and http_method == 'POST':
        logger.info("Handling post request for /teco-profile-config")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_profile_configs(body)
    elif resource == '/dashboards' and http_method == 'GET':
        logger.info("Handling GET request for /teco-profile-dashboard")

        # Query String Parameters
        email = query_params.get('email', '')

        logger.info(f"email: {email}")

        return handle_get_profile_dashboard(email)
    elif resource == '/list-connect-agents' and http_method == 'GET':
        logger.info("Handling GET request for /list-connect-agents")

        return handle_get_list_connect_agents()    
    elif resource == '/agent-proficiency-assignment' and http_method == 'POST':
        logger.info("Handling post request for /agent-proficiency-assignment")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_agent_proficiency_assignment(body)
    elif resource == '/agent-proficiency-profiles' and http_method == 'POST':
        logger.info("Handling post request for /agent-proficiency-profile")

        body = json.loads(body)

        logger.info(f"Body: {body}")

        return handle_agent_proficiency_profiles(body)        

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

