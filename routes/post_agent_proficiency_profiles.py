from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import boto3
import json
import uuid
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

# ---------------- Logging ----------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------- DynamoDB ----------------
dynamodb = DDB
table = dynamodb.Table("teco-proficiency-profile-us-east-1-dev")

# ---------------- Helpers -----------------
def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    }

def respond(status_code: int, payload: dict):
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(payload),
    }

# ---------------- Main Handler -----------------
def handle_agent_proficiency_profiles(body):
    """
    Supported actions:
      - create
      - update
      - delete
      - list
      - getByProfile
      - listOptions          <-- NEW: for dropdowns
      - addProficiency
      - removeProficiency
    """

    action = body.get("action")
    logger.info(f"Action received: {action}")

    try:
        # ---------- CREATE ----------
        if action == "create":
            # Always generate a new UUID
            new_id = str(uuid.uuid4())
            table.put_item(
                Item={
                    "profile_name": body["profile_name"],
                    "profile_id": new_id,                                # NEW field
                    "proficiencies": body.get("proficiencies", []),
                }
            )
            return respond(200, {
                "message": "Profile created successfully",
                "profile_id": new_id                                    # return ID to caller
            })

        # ---------- UPDATE ----------
        elif action == "update":
            table.update_item(
                Key={"profile_name": body["profile_name"]},
                UpdateExpression="SET proficiencies = :p",
                ExpressionAttributeValues={
                    ":p": body.get("proficiencies", [])
                },
            )
            return respond(200, {"message": "Profile updated successfully"})

        # ---------- ADD PROFICIENCY ----------
        elif action == "addProficiency":
            new_prof = body.get("proficiency")
            if not new_prof:
                return respond(400, {"error": "Missing proficiency to add"})

            # Fetch current proficiencies
            current = table.get_item(Key={"profile_name": body["profile_name"]}).get("Item", {})
            profs = set(current.get("proficiencies", []))
            profs.add(new_prof)

            table.update_item(
                Key={"profile_name": body["profile_name"]},
                UpdateExpression="SET proficiencies = :p",
                ExpressionAttributeValues={":p": list(profs)},
            )
            return respond(200, {"message": "Proficiency added successfully"})

        # ---------- REMOVE PROFICIENCY ----------
        elif action == "removeProficiency":
            remove_prof = body.get("proficiency")
            if not remove_prof:
                return respond(400, {"error": "Missing proficiency to remove"})

            current = table.get_item(Key={"profile_name": body["profile_name"]}).get("Item", {})
            profs = current.get("proficiencies", [])

            if remove_prof in profs:
                profs.remove(remove_prof)
                table.update_item(
                    Key={"profile_name": body["profile_name"]},
                    UpdateExpression="SET proficiencies = :p",
                    ExpressionAttributeValues={":p": profs},
                )
                return respond(200, {"message": "Proficiency removed successfully"})
            else:
                return respond(404, {"error": "Proficiency not found"})

        # ---------- DELETE ----------
        elif action == "delete":
            table.delete_item(Key={"profile_name": body["profile_name"]})
            return respond(200, {"message": "Profile deleted successfully"})

        # ---------- LIST ALL ----------
        elif action == "list":
            res = table.scan()
            return respond(200, {"profiles": res.get("Items", [])})

        # ---------- LIST OPTIONS (for dropdown) ----------
        elif action == "listOptions":
            res = table.scan()
            options = [
                {"id": i.get("profile_id"), "name": i.get("profile_name")}
                for i in res.get("Items", [])
                if i.get("profile_id")
            ]
            return respond(200, {"options": options})

        # ---------- GET BY PROFILE ----------
        elif action == "getByProfile":
            res = table.get_item(Key={"profile_name": body["profile_name"]})
            return respond(200, {"profile": res.get("Item", {})})

        # ---------- INVALID ----------
        else:
            return respond(400, {"error": "Invalid action"})

    except Exception as e:
        logger.exception("Unhandled error during profile proficiency operation")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
