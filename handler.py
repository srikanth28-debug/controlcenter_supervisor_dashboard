import json
import logging

# Import get_logger instead of logger
from utils.logger import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# Import your route handlers
# from routes.get_greetings import handle_get_greetings
# from routes.post_greetings import handle_post_greetings
from routes.get_voices import handle_get_voices
from routes.post_speech import handle_post_speech
from routes.get_predefined_attributes import handle_get_predefined_attributes
from routes.delete_predefined_attribute import handle_delete_predefined_attributes
from routes.post_predefined_attributes import handle_post_predefined_attributes
from routes.get_email_template import handle_get_email_template_app
from routes.post_task_template import handle_post_task_template_app
from routes.post_chaneltype_configs import handle_chaneltype_configs
from routes.post_chaneltype_prompts import handle_chaneltype_prompts
from routes.post_user_config import handle_user_configs
from routes.post_profile_config import handle_profile_configs
from routes.get_profile_dashboards import handle_get_profile_dashboard
from routes.post_agent_proficiency_profiles import handle_agent_proficiency_profiles
from routes.post_agent_proficiency_assignment import handle_agent_proficiency_assignment


def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    resource = event.get('resource', '')
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')
    query_params = event.get('queryStringParameters') or {}
    path_params = event.get('pathParameters') or {}
    body = event.get('body', '{}')

    logger.info(f"Path: {path}, Resource: {resource}, Method: {http_method}")

    # --- CORS Preflight ---
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

    # --- Routing Logic ---
    try:
        if resource == '/agent-greeting' and http_method == 'GET':
            return handle_get_greetings(
                query_params.get('username', ''), query_params.get('language', '')
            )
        elif resource == '/agent-greeting' and http_method == 'POST':
            return handle_post_greetings(json.loads(body))
        elif resource == '/polly/languages' and http_method == 'GET':
            return handle_get_voices()
        elif resource == '/polly/speech' and http_method == 'POST':
            return handle_post_speech(json.loads(body))
        elif resource == '/business-configuration/users' and http_method == 'GET':
            return handle_get_users()
        elif resource == '/admin-configuration/predefined-attributes' and http_method == 'GET':
            return handle_get_predefined_attributes()
        elif resource == '/admin-configuration/predefined-attributes/{attributeName+}' and http_method == 'DELETE':
            return handle_delete_predefined_attributes(path_params)
        elif resource == '/admin-configuration/predefined-attributes' and http_method == 'POST':
            return handle_post_predefined_attributes(json.loads(body))
        elif resource == '/business-configuration/user-proficiencies' and http_method == 'POST':
            return handle_post_user_proficiencies(json.loads(body))
        elif resource == '/business-configuration/user-proficiencies-bulk' and http_method == 'POST':
            return handle_post_user_proficiencies_bulk(json.loads(body))
        elif resource == '/email-template-app/{routingProfile+}' and http_method == 'GET':
            return handle_get_email_template_app(path_params)
        elif resource == '/task-template-app' and http_method == 'POST':
            return handle_post_task_template_app(json.loads(body))
        elif resource == '/chaneltypeconfigs' and http_method == 'POST':
            return handle_chaneltype_configs(json.loads(body))
        elif resource == '/chaneltypeprompts' and http_method == 'POST':
            return handle_chaneltype_prompts(json.loads(body))
        elif resource == '/userconfig' and http_method == 'POST':
            return handle_user_configs(json.loads(body))
        elif resource == '/profileconfig' and http_method == 'POST':
            return handle_profile_configs(json.loads(body))
        elif resource == '/dashboards' and http_method == 'GET':
            return handle_get_profile_dashboard(query_params.get('email', ''))
        elif resource == '/agent-proficiency-assignment' and http_method == 'POST':
            return handle_agent_proficiency_assignment(json.loads(body))
        elif resource == '/agent-proficiency-profiles' and http_method == 'POST':
            return handle_agent_proficiency_profiles(json.loads(body))
        else:
            logger.warning(f"No matching route for resource: {resource}, method: {http_method}")
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"message": f"No route found for {resource} [{http_method}]"}),
            }

    except Exception as e:
        logger.exception(f"Error handling {resource}: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
