from utils.aws_clients import table
from utils.logger import get_logger
from utils.http import respond
import os

logger = get_logger(__name__)

# Resolve tables dynamically using environment variables
USER_PERMISSION_TABLE = table("DDB_TABLE_TECO_USER_PERMISSION_REACT_TABLE")
PROFILE_DASHBOARD_TABLE = table("DDB_TABLE_TECO_PROFILE_PERMISSIONS_REACT_TABLE")

def handle_get_profile_dashboard(email: str):
    """
    Fetches profile dashboard configuration for a user based on their email.
    1. Retrieves user's security profile & team from USER_PERMISSION_TABLE.
    2. Uses those to query PROFILE_DASHBOARD_TABLE for tab configuration.
    """

    try:
        if not email:
            logger.warning("Email missing in request")
            return respond(400, {"error": "Email not found in token"})

        # Step 1: Fetch user details
        user_res = USER_PERMISSION_TABLE.get_item(Key={"username": email})
        if "Item" not in user_res:
            logger.info(f"User not found for email: {email}")
            return respond(404, {"error": "User not found"})

        user_item = user_res["Item"]
        security_profile = user_item.get("security_profile")
        team = user_item.get("team")
        team_display = user_item.get("team_display")
        security_profile_display = user_item.get("security_profile_display")

        if not security_profile or not team:
            logger.warning(f"Incomplete user data for {email}")
            return respond(400, {"error": "Missing security profile or team info"})

        # Step 2: Query dashboard config
        dash_res = PROFILE_DASHBOARD_TABLE.get_item(
            Key={"security_profile": security_profile, "team": team}
        )

        if "Item" not in dash_res:
            logger.info(f"No tab configuration for profile={security_profile}, team={team}")
            return respond(404, {"error": "No tab config found"})

        tab_list = dash_res["Item"].get("tabnames", [])

        # Step 3: Build response
        result = {
            "email": email,
            "securityProfile": security_profile,
            "team": team,
            "teamDisplay": team_display,
            "securityProfileDisplay": security_profile_display,
            "tabs": tab_list
        }

        logger.info(f"Profile dashboard fetched successfully for {email}")
        return respond(200, result)

    except Exception as e:
        logger.exception("Error while fetching profile dashboard")
        return respond(500, {
            "error": "InternalServerError",
            "message": str(e)
        })
