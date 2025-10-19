from utils.aws_clients import ddb as DDB, table
from utils.logger import get_logger
from utils.http import respond
import os

# ---------------------------------------------------------------------------
# Logging & AWS Clients
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
dynamodb = DDB

# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------
USER_PERMISSION_TABLE_NAME = os.environ["DDB_TABLE_TECO_USER_PERMISSION_REACT_TABLE"]
user_permission_table = dynamodb.Table(USER_PERMISSION_TABLE_NAME)

PROFILE_PERMISSIONS_TABLE_NAME = os.environ["DDB_TABLE_TECO_PROFILE_PERMISSIONS_REACT_TABLE"]
profile_permission_table = dynamodb.Table(PROFILE_PERMISSIONS_TABLE_NAME)

# ---------------------------------------------------------------------------
# Main Handler
# ---------------------------------------------------------------------------
def handle_user_configs(body: dict):

    action = body.get("action")
    username = body.get("username")

    if not action:
        logger.warning("[WARN] Missing 'action' in request body")
        return respond(400, {"error": "Missing 'action' parameter"})

    try:
        logger.info(f"[REQUEST] action={action}, username={username}")
        logger.info(f"[TABLE] Using DynamoDB Table: {USER_PERMISSION_TABLE_NAME}")

        # ---------- CREATE ----------
        if action == "create":
            user_permission_table.put_item(
                Item={
                    "username": body["username"],
                    "team": body["team"],
                    "security_profile": body["security_profile"],
                    "team_display": body["teamDisplay"],
                    "security_profile_display": body["securityProfileDisplay"]
                }
            )
            logger.info(f"[CREATE] User created: {username}")
            return respond(200, {"message": "User created successfully"})

        # ---------- UPDATE ----------
        elif action == "update":
            user_permission_table.update_item(
                Key={"username": body["username"]},
                UpdateExpression="SET team = :t, security_profile = :s, security_profile_display = :sd, team_display = :td",
                ExpressionAttributeValues={
                    ":t": body["team"],
                    ":s": body["security_profile"],
                    ":sd": body["securityProfileDisplay"],
                    ":td": body["teamDisplay"]
                }
            )
            logger.info(f"[UPDATE] User updated: {username}")
            return respond(200, {"message": "User updated successfully"})

        # ---------- DELETE ----------
        elif action == "delete":
            user_permission_table.delete_item(Key={"username": body["username"]})
            logger.info(f"[DELETE] User deleted: {username}")
            return respond(200, {"message": "User deleted successfully"})

        # ---------- LIST USERS ----------
        elif action == "list":
            res = user_permission_table.scan()
            users = res.get("Items", [])
            logger.info(f"[LIST] Retrieved {len(users)} users")
            return respond(200, {"users": users})

        # ---------- LIST TEAMS + SECURITY PROFILES ----------
        elif action == "listTeamsProfiles":
            res = profile_permission_table.scan()
            items = res.get("Items", [])

            teams = {}
            access_levels = {}

            for item in items:
                # Team
                team_key = item.get("team")
                team_display = item.get("team_display")
                if team_key and team_display:
                    teams[team_key] = team_display
                
                # Access level / Security Profile
                access_key = item.get("security_profile")
                access_display = item.get("security_profile_display")
                if access_key and access_display:
                    access_levels[access_key] = access_display

            # Convert to desired array of objects
            teams_list = [{"team": k, "teamDisplay": v} for k, v in teams.items()]
            access_levels_list = [{"accessLevel": k, "accessLevelDisplay": v} for k, v in access_levels.items()]

            logger.info(f"[LIST-TEAMS-PROFILES] Teams={len(teams_list)}, AccessLevels={len(access_levels_list)}")
            return respond(200, {"teams": teams_list, "accessLevels": access_levels_list})

        # ---------- INVALID ----------
        else:
            logger.warning(f"[INVALID] Unsupported action: {action}")
            return respond(400, {"error": f"Unsupported action '{action}'"})

    except Exception as e:
        logger.exception(f"[ERROR] Exception processing user config for {username}")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
