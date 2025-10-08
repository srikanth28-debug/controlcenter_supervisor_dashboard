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

def _deprecated_local_response(status_code: int, payload: dict):
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
            return _response(200, {
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
            return _response(200, {"message": "Profile updated successfully"})

        # ---------- ADD PROFICIENCY ----------
        elif action == "addProficiency":
            new_prof = body.get("proficiency")
            if not new_prof:
                return _response(400, {"error": "Missing proficiency to add"})

            # Fetch current proficiencies
            current = table.get_item(Key={"profile_name": body["profile_name"]}).get("Item", {})
            profs = set(current.get("proficiencies", []))
            profs.add(new_prof)

            table.update_item(
                Key={"profile_name": body["profile_name"]},
                UpdateExpression="SET proficiencies = :p",
                ExpressionAttributeValues={":p": list(profs)},
            )
            return _response(200, {"message": "Proficiency added successfully"})

        # ---------- REMOVE PROFICIENCY ----------
        elif action == "removeProficiency":
            remove_prof = body.get("proficiency")
            if not remove_prof:
                return _response(400, {"error": "Missing proficiency to remove"})

            current = table.get_item(Key={"profile_name": body["profile_name"]}).get("Item", {})
            profs = current.get("proficiencies", [])

            if remove_prof in profs:
                profs.remove(remove_prof)
                table.update_item(
                    Key={"profile_name": body["profile_name"]},
                    UpdateExpression="SET proficiencies = :p",
                    ExpressionAttributeValues={":p": profs},
                )
                return _response(200, {"message": "Proficiency removed successfully"})
            else:
                return _response(404, {"error": "Proficiency not found"})

        # ---------- DELETE ----------
        elif action == "delete":
            table.delete_item(Key={"profile_name": body["profile_name"]})
            return _response(200, {"message": "Profile deleted successfully"})

        # ---------- LIST ALL ----------
        elif action == "list":
            res = table.scan()
            return _response(200, {"profiles": res.get("Items", [])})

        # ---------- LIST OPTIONS (for dropdown) ----------
        elif action == "listOptions":
            res = table.scan()
            options = [
                {"id": i.get("profile_id"), "name": i.get("profile_name")}
                for i in res.get("Items", [])
                if i.get("profile_id")
            ]
            return _response(200, {"options": options})

        # ---------- GET BY PROFILE ----------
        elif action == "getByProfile":
            res = table.get_item(Key={"profile_name": body["profile_name"]})
            return _response(200, {"profile": res.get("Item", {})})

        # ---------- INVALID ----------
        else:
            return _response(400, {"error": "Invalid action"})

    except Exception as e:
        logger.exception("Unhandled error during profile proficiency operation")
        return _response(500, {"error": "InternalServerError", "message": str(e)})

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

