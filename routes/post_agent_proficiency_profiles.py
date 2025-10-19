from utils.aws_clients import ddb as DDB, connect as CONNECT
from utils.logger import get_logger
from utils.http import respond
import os, json, uuid, time
from datetime import timezone
from botocore.exceptions import ClientError

logger = get_logger(__name__)
dynamodb = DDB
connect = CONNECT

INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
PROFILE_TABLE = os.environ["DDB_TABLE_TECO_PROFICIENCY_PROFILE_US_EAST_1_DEV"]
profile_table = dynamodb.Table(PROFILE_TABLE)

_CACHE = {"timestamp": 0, "ttl": 300, "data": None}

# ---------------------------------------------------------------------------
# CONNECT ATTRIBUTE HELPERS
# ---------------------------------------------------------------------------

def _paginate_list_predefined_attributes(instance_id):
    paginator = connect.get_paginator("list_predefined_attributes")
    for page in paginator.paginate(InstanceId=instance_id):
        for s in page.get("PredefinedAttributeSummaryList", []):
            yield s


def _describe_attribute(instance_id, name):
    try:
        resp = connect.describe_predefined_attribute(InstanceId=instance_id, Name=name)
        pa = resp.get("PredefinedAttribute", {}) or {}
        values = (pa.get("Values") or {}).get("StringList", [])
        return {"name": pa.get("Name") or name, "values": values}
    except ClientError as e:
        err = e.response.get("Error", {}).get("Message", str(e))
        logger.warning(f"Failed to describe attribute '{name}': {err}")
        return {"name": name, "values": []}


def _fetch_predefined_proficiencies():
    """Return flattened list of proficiencies like Attribute=Value (Lx)."""
    attributes, combined = [], []
    index = 1
    for summary in _paginate_list_predefined_attributes(INSTANCE_ID):
        name = summary.get("Name")
        if not name:
            continue
        detail = _describe_attribute(INSTANCE_ID, name)
        attributes.append(detail)
        for val in detail["values"] or []:
            combined.append(f"{detail['name']}={val} (L{index})")
            index += 1
    combined.sort(key=lambda x: x.lower())
    return {"proficiencies": combined, "rawAttributes": attributes}


def _get_cached_predefined_proficiencies():
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["timestamp"] < _CACHE["ttl"]):
        return _CACHE["data"]
    data = _fetch_predefined_proficiencies()
    _CACHE.update({"data": data, "timestamp": now})
    return data


# ---------------------------------------------------------------------------
# MAIN HANDLER
# ---------------------------------------------------------------------------

def handle_agent_proficiency_profiles(body):
    action = body.get("action")
    logger.info(f"[ACTION] {action}")

    try:
        # ---------- CREATE ----------
        if action == "create":
            new_id = str(uuid.uuid4())
            profile_table.put_item(
                Item={
                    "profile_name": body["profile_name"],
                    "profile_id": new_id,
                    "proficiencies": body.get("proficiencies", []),
                }
            )
            return respond(200, {"message": "Profile created", "profile_id": new_id})

        # ---------- UPDATE ----------
        elif action == "update":
            profile_table.update_item(
                Key={"profile_name": body["profile_name"]},
                UpdateExpression="SET proficiencies = :p",
                ExpressionAttributeValues={":p": body.get("proficiencies", [])},
            )
            return respond(200, {"message": "Profile updated"})

        # ---------- DELETE ----------
        elif action == "delete":
            profile_table.delete_item(Key={"profile_name": body["profile_name"]})
            return respond(200, {"message": "Profile deleted"})

        # ---------- LIST ----------
        elif action == "list":
            res = profile_table.scan()
            return respond(200, {"profiles": res.get("Items", [])})

        # ---------- LIST OPTIONS ----------
        elif action == "listOptions":
            res = profile_table.scan()
            options = [
                {"id": i.get("profile_id"), "name": i.get("profile_name")}
                for i in res.get("Items", [])
                if i.get("profile_id")
            ]
            return respond(200, {"options": options})

        # ---------- GET BY PROFILE ----------
        elif action == "getByProfile":
            res = profile_table.get_item(Key={"profile_name": body["profile_name"]})
            return respond(200, {"profile": res.get("Item", {})})

        # ---------- LIST PREDEFINED PROFICIENCIES ----------
        elif action == "listPredefinedProficiencies":
            data = _get_cached_predefined_proficiencies()
            logger.info(f"Returned {len(data['proficiencies'])} proficiencies")
            return respond(200, data)

        # ---------- INVALID ----------
        else:
            return respond(400, {"error": f"Invalid action '{action}'"})

    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        logger.warning(f"[AWS ERROR] {code}: {msg}")
        return respond(502, {"error": code, "message": msg})

    except Exception as e:
        logger.exception("[ERROR] Unhandled exception in handle_agent_proficiency_profiles")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
