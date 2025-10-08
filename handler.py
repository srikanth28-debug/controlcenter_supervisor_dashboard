import json
from utils.logger import get_logger
from utils.http import respond, cors_headers

logger = get_logger("router")

def _import(name, func):
    try:
        mod = __import__(f"routes.{name}", fromlist=[func])
        return getattr(mod, func)
    except Exception:
        return None

# Try to import handlers; any can be None if module missing
handle_agent_proficiency_assignment = _import("post_agent_proficiency_assignment", "handle_agent_proficiency_assignment")
handle_agent_proficiency_profiles   = _import("post_agent_proficiency_profiles", "handle_agent_proficiency_profiles")
handle_chaneltype_configs           = _import("post_chaneltype_configs", "handle_chaneltype_configs")
handle_chaneltype_prompts           = _import("post_chaneltype_prompts", "handle_chaneltype_prompts")
handle_get_users                    = _import("get_users", "handle_get_users")
handle_get_profile_dashboard        = _import("get_profile_dashboards", "handle_get_profile_dashboard")
handle_get_predefined_attributes    = _import("get_predefined_attributes", "handle_get_predefined_attributes")
handle_post_predefined_attributes   = _import("post_predefined_attributes", "handle_post_predefined_attributes")
handle_delete_predefined_attributes = _import("delete_predefined_attribute", "handle_delete_predefined_attributes")
handle_get_greetings                = _import("get_greetings", "handle_get_greetings")
handle_post_greetings               = _import("post_greetings", "handle_post_greetings")
handle_get_voices                   = _import("get_voices", "handle_get_voices")
handle_post_speech                  = _import("post_speech", "handle_post_speech")
handle_post_user_config             = _import("post_user_config", "handle_post_user_config")
handle_post_profile_config          = _import("post_profile_config", "handle_post_profile_config")
handle_post_task_template_app       = _import("post_task_template", "handle_post_task_template_app")
handle_post_user_proficiencies      = _import("post_user_proficiencies", "handle_post_user_proficiencies")
handle_post_user_proficiencies_bulk = _import("post_user_proficiencies_bulk", "handle_post_user_proficiencies_bulk")
handle_get_list_connect_agents      = _import("get_list_connect_agents", "handle_get_list_connect_agents")
handle_get_email_template           = _import("get_email_template", "handle_get_email_template")

def _parse_body(event):
    body = event.get("body")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except Exception:
            return {}
    return body or {}

def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": cors_headers(), "body": ""}

    path = event.get("resource") or event.get("path") or ""
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    body = _parse_body(event)
    logger.info(f"{method} {path}")

    if path.endswith("/agent-proficiency-assignment") and method == "POST" and handle_agent_proficiency_assignment:
        return handle_agent_proficiency_assignment(body)
    if path.endswith("/agent-proficiency-profiles") and method == "POST" and handle_agent_proficiency_profiles:
        return handle_agent_proficiency_profiles(body)
    if path.endswith("/chaneltypeconfigs") and method == "POST" and handle_chaneltype_configs:
        return handle_chaneltype_configs(body)
    if path.endswith("/chaneltypeprompts") and method == "POST" and handle_chaneltype_prompts:
        return handle_chaneltype_prompts(body)
    if path.endswith("/users") and method == "POST" and handle_get_users:
        return handle_get_users(body)
    if path.endswith("/profile-dashboards") and method == "POST" and handle_get_profile_dashboard:
        return handle_get_profile_dashboard(body)
    if path.endswith("/predefined-attributes") and method == "GET" and handle_get_predefined_attributes:
        return handle_get_predefined_attributes(body)
    if path.endswith("/predefined-attributes") and method == "POST" and handle_post_predefined_attributes:
        return handle_post_predefined_attributes(body)
    if path.endswith("/predefined-attributes") and method == "DELETE" and handle_delete_predefined_attributes:
        return handle_delete_predefined_attributes(body)
    if path.endswith("/greetings") and method == "GET" and handle_get_greetings:
        return handle_get_greetings(body)
    if path.endswith("/greetings") and method == "POST" and handle_post_greetings:
        return handle_post_greetings(body)
    if path.endswith("/voices") and method == "GET" and handle_get_voices:
        return handle_get_voices(body)
    if path.endswith("/speech") and method == "POST" and handle_post_speech:
        return handle_post_speech(body)
    if path.endswith("/user-config") and method == "POST" and handle_post_user_config:
        return handle_post_user_config(body)
    if path.endswith("/profile-config") and method == "POST" and handle_post_profile_config:
        return handle_post_profile_config(body)
    if path.endswith("/task-template") and method == "POST" and handle_post_task_template_app:
        return handle_post_task_template_app(body)
    if path.endswith("/user-proficiencies") and method == "POST" and handle_post_user_proficiencies:
        return handle_post_user_proficiencies(body)
    if path.endswith("/user-proficiencies-bulk") and method == "POST" and handle_post_user_proficiencies_bulk:
        return handle_post_user_proficiencies_bulk(body)
    if path.endswith("/list-connect-agents") and method == "POST" and handle_get_list_connect_agents:
        return handle_get_list_connect_agents(body)
    if path.endswith("/email-template") and method == "POST" and handle_get_email_template:
        return handle_get_email_template(body)

    return respond(404, {"error": f"No route for {method} {path}"})
