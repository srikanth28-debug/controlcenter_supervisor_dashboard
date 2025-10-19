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
PROFILE_PERMISSIONS_TABLE_NAME = os.environ["DDB_TABLE_TECO_PROFILE_PERMISSIONS_REACT_TABLE"]
profile_permissions_table = dynamodb.Table(PROFILE_PERMISSIONS_TABLE_NAME)


# Utility function to normalize display names
def normalize_display_string(display_str):
    return ", ".join(
        name.strip().lower().replace(" ", "_")
        for name in display_str.split(",")
        if name.strip()
    )

# ---------------------------------------------------------------------------
# Main Handler
# ---------------------------------------------------------------------------
def handle_profile_configs(body: dict):

    action = body.get("action")
    securityprofile = body.get("securityprofile")

    try:
        logger.info(f"[REQUEST] Action={action}, SecurityProfile={securityprofile}")
        logger.info(f"[TABLE] Using DynamoDB Table: {PROFILE_PERMISSIONS_TABLE_NAME}")

        # ---------- CREATE ----------
        if action == "create":
            # Example usage inside your logic
            security_profile_display = body["security_profile_display"]
            team_display = body["team_display"]

            security_profile = normalize_display_string(security_profile_display)
            team = normalize_display_string(team_display)

            profile_permissions_table.put_item(
                Item={
                    "security_profile": security_profile,
                    "team": team,
                    "tabnames": body["tabnames"],
                    "security_profile_display": body["security_profile_display"],
                    "team_display": body["team_display"]
                }
            )
            logger.info(f"[CREATE] Created profile config for {securityprofile}")
            return respond(200, {"message": "User created"})

        # ---------- UPDATE ----------
        elif action == "update":
            profile_permissions_table.update_item(
                Key={
                    "security_profile": body["security_profile"],
                    "team": body["team"]
                },
                UpdateExpression="SET tabnames = :t",
                ExpressionAttributeValues={":t": body["tabnames"]}
            )
            logger.info(f"[UPDATE] Updated profile config for {securityprofile}")
            return respond(200, {"message": "User updated"})

        # ---------- DELETE ----------
        elif action == "delete":
            profile_permissions_table.delete_item(
                Key={
                    "securityprofile": body["securityprofile"],
                    "team": body["team"]
                }
            )
            logger.info(f"[DELETE] Deleted profile config for {securityprofile}")
            return respond(200, {"message": "User deleted"})

        # ---------- LIST ----------
        elif action == "list":
            res = profile_permissions_table.scan()
            items = res.get("Items", [])
            logger.info(f"[LIST] Fetched {len(items)} users")
            return respond(200, {"users": items})

        # ---------- LIST TEAMS + TABS ----------
        elif action == "listTeamsTabs":
            res = profile_permissions_table.scan()
            items = res.get("Items", [])

            teams = sorted({item.get("team") for item in items if item.get("team")})
            tabs = set()

            for item in items:
                tabnames = item.get("tabnames", [])
                if isinstance(tabnames, list):
                    for t in tabnames:
                        if isinstance(t, dict) and "S" in t:
                            tabs.add(t["S"])
                        else:
                            tabs.add(str(t))

            logger.info(f"[LIST-TEAMS-TABS] Teams={len(teams)}, Tabs={len(tabs)}")
            return respond(200, {"teams": list(teams), "tabs": list(tabs)})

        # ---------- INVALID ----------
        else:
            logger.warning(f"[INVALID] Unsupported action: {action}")
            return respond(400, {"error": f"Unsupported action '{action}'"})

    except Exception as e:
        logger.exception("[ERROR] Unhandled exception in handle_profile_configs")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
